from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest
import quickstart
import yaml

ROOT = Path(__file__).resolve().parents[2]
RAG = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))
APP = yaml.safe_load((ROOT / "config" / "app.yaml").read_text(encoding="utf-8"))
MODELS = {RAG["embed"]["serving_name"], RAG["compose"]["serving_name"]}
OLLAMA_HEADER = "NAME                ID              SIZE      MODIFIED\n"


# ------------------------------------------------------------ fakes (no network, no processes)
class FakeProc:
    def __init__(self, code: int = 0, alive: bool = True) -> None:
        self.code = code
        self._alive = alive
        self.waited = False

    def poll(self) -> int | None:
        return None if self._alive else self.code

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        self._alive = False
        return self.code


class FakeShell:
    def __init__(
        self,
        *,
        tools: Sequence[str] = ("uv", "node", "pnpm", "ollama"),
        versions: dict[str, str] | None = None,
        ollama_list: tuple[int, str] | None = None,
        fail_on: str | None = None,
        proc: FakeProc | None = None,
    ) -> None:
        self.tools = set(tools)
        self.versions = versions or {"node": "v20.11.1\n", "pnpm": "10.18.0\n"}
        default_list = OLLAMA_HEADER + "".join(f"{m} abc 1 GB now\n" for m in sorted(MODELS))
        self.ollama_list = ollama_list or (0, default_list)
        self.fail_on = fail_on
        self.proc = proc or FakeProc()
        self.ran: list[list[str]] = []
        self.spawned: list[tuple[list[str], dict[str, str]]] = []

    def which(self, name: str) -> str | None:
        return f"/bin/{name}" if name in self.tools else None

    def capture(self, cmd: Sequence[str]) -> tuple[int, str]:
        if list(cmd) == ["ollama", "list"]:
            return self.ollama_list
        return 0, self.versions.get(cmd[0], "1.0.0\n")

    def run(self, cmd: Sequence[str]) -> int:
        self.ran.append(list(cmd))
        return 1 if self.fail_on and self.fail_on in " ".join(cmd) else 0

    def spawn(self, cmd: Sequence[str], env: dict[str, str]) -> FakeProc:
        self.spawned.append((list(cmd), env))
        return self.proc


def make_root(tmp_path: Path, *, with_index: bool) -> Path:
    for rel in ("config/app.yaml", "config/rag.yaml", "package.json", "data/sources.yaml"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    if with_index:
        index = tmp_path / RAG["kb"]["index_dir"]
        index.mkdir(parents=True)
        (index / "index_meta.json").write_text("{}", encoding="utf-8")
    return tmp_path


def make_deps(shell: FakeShell, *, probe_ok: bool = True, answer: str = "y") -> quickstart.Deps:
    opened: list[str] = []
    ticks = iter(range(100_000))
    deps = quickstart.Deps(
        shell=shell,
        probe=lambda url: probe_ok,
        open_url=lambda url: opened.append(url) is None,
        ask=lambda prompt: answer,
        environ={"PATH": "x"},
        clock=lambda: float(next(ticks)),
        sleep=lambda s: None,
    )
    deps.opened = opened  # type: ignore[attr-defined]
    return deps


# ------------------------------------------------------------------ config and arguments
def test_load_config_reads_models_ports_and_index_from_config(tmp_path: Path) -> None:
    cfg = quickstart.load_config(make_root(tmp_path, with_index=False))
    assert set(cfg.models) == MODELS
    assert cfg.index_meta == tmp_path / RAG["kb"]["index_dir"] / "index_meta.json"
    assert f":{APP['ports']['web']}/" in cfg.web_url
    assert f":{APP['ports']['api']}/" in cfg.health_url
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert str(cfg.min_versions["node"]) in pkg["engines"]["node"]
    assert cfg.portal == RAG["kb"]["source_portal"]


def test_parse_args_flags() -> None:
    args = quickstart.parse_args(["--check", "--no-data", "--no-browser", "--yes"])
    assert (args.check, args.no_data, args.no_browser, args.yes) == (True, True, True, True)
    args = quickstart.parse_args([])
    assert (args.check, args.no_data, args.no_browser, args.yes) == (False, False, False, False)


# ------------------------------------------------------------------ pure helpers
def test_parse_ollama_list_strips_latest_and_header() -> None:
    text = OLLAMA_HEADER + "bge-m3:latest  x  1 GB  now\nqwen3.5:2b  y  2 GB  now\n\n"
    assert quickstart.parse_ollama_list(text) == {"bge-m3", "bge-m3:latest", "qwen3.5:2b"}


def test_missing_models_keeps_config_order() -> None:
    assert quickstart.missing_models({"bge-m3"}, ("bge-m3", "qwen3.5:2b")) == ["qwen3.5:2b"]
    assert quickstart.missing_models(set(), ("a", "b")) == ["a", "b"]


@pytest.mark.parametrize(
    ("text", "major"), [("v20.11.1", 20), ("10.18.0\n", 10), ("v8", 8), ("garbage", None)]
)
def test_version_major(text: str, major: int | None) -> None:
    assert quickstart.version_major(text) == major


def test_install_help_names_every_missing_tool_without_piping_to_a_shell() -> None:
    text = quickstart.install_help(["uv", "ollama"], {"node": 20, "pnpm": 10})
    assert "uv" in text and "ollama" in text
    assert "| sh" not in text and "| bash" not in text and "iex" not in text


def test_build_plan_full_and_minimal(tmp_path: Path) -> None:
    cfg = quickstart.load_config(make_root(tmp_path, with_index=False))
    plan = quickstart.build_plan(cfg, ["bge-m3"], with_data=True)
    cmds = [s.cmd for s in plan]
    assert cmds[0] == ["ollama", "pull", "bge-m3"]
    assert ["uv", "sync", "--all-packages"] in cmds
    assert ["pnpm", "install", "--frozen-lockfile"] in cmds
    pipeline = ["uv", "run", "python", "-m", "ctcv_data.pipeline"]
    assert cmds[-3:] == [
        [*pipeline, "crawl", "--online"],
        [*pipeline, "normalize"],
        [*pipeline, "chunk_embed", "--online"],
    ]
    assert "robots" in plan[-3].note
    minimal = quickstart.build_plan(cfg, [], with_data=False)
    assert [s.cmd[0] for s in minimal] == ["uv", "pnpm"]


# ------------------------------------------------------------------ main: checks
def test_missing_tool_prints_help_and_runs_nothing(tmp_path: Path, capsys) -> None:
    shell = FakeShell(tools=("uv", "node", "pnpm"))
    code = quickstart.main([], deps=make_deps(shell), root=make_root(tmp_path, with_index=True))
    assert code == 2
    assert "ollama" in capsys.readouterr().out.lower()
    assert shell.ran == [] and shell.spawned == []


def test_old_node_is_reported(tmp_path: Path, capsys) -> None:
    shell = FakeShell(versions={"node": "v18.19.0\n", "pnpm": "10.1.0\n"})
    code = quickstart.main([], deps=make_deps(shell), root=make_root(tmp_path, with_index=True))
    assert code == 2
    assert "node" in capsys.readouterr().out.lower()
    assert shell.ran == []


def test_ollama_not_running_is_reported(tmp_path: Path, capsys) -> None:
    shell = FakeShell(ollama_list=(1, "could not connect"))
    code = quickstart.main([], deps=make_deps(shell), root=make_root(tmp_path, with_index=True))
    assert code == 2
    assert "Ollama" in capsys.readouterr().out
    assert shell.ran == []


def test_check_mode_runs_nothing(tmp_path: Path, capsys) -> None:
    shell = FakeShell(ollama_list=(0, OLLAMA_HEADER))
    root = make_root(tmp_path, with_index=False)
    code = quickstart.main(["--check"], deps=make_deps(shell), root=root)
    out = capsys.readouterr().out
    assert code == 0
    assert shell.ran == [] and shell.spawned == []
    for model in MODELS:
        assert f"ollama pull {model}" in out


def test_no_data_without_index_stops_before_running(tmp_path: Path, capsys) -> None:
    shell = FakeShell()
    root = make_root(tmp_path, with_index=False)
    code = quickstart.main(["--no-data", "--yes"], deps=make_deps(shell), root=root)
    assert code == 2
    assert "chunk_embed" in capsys.readouterr().out
    assert shell.ran == []


def test_declined_confirmation_runs_nothing(tmp_path: Path) -> None:
    shell = FakeShell()
    root = make_root(tmp_path, with_index=True)
    code = quickstart.main([], deps=make_deps(shell, answer="n"), root=root)
    assert code == 1
    assert shell.ran == [] and shell.spawned == []


# ------------------------------------------------------------------ main: full run
def test_full_run_pulls_models_builds_data_and_opens_citizen_page(tmp_path: Path) -> None:
    shell = FakeShell(ollama_list=(0, OLLAMA_HEADER))
    root = make_root(tmp_path, with_index=False)
    index_meta = root / RAG["kb"]["index_dir"] / "index_meta.json"

    def run(cmd: Sequence[str]) -> int:
        shell.ran.append(list(cmd))
        if "chunk_embed" in cmd:
            index_meta.parent.mkdir(parents=True, exist_ok=True)
            index_meta.write_text("{}", encoding="utf-8")
        return 0

    shell.run = run  # type: ignore[method-assign]
    deps = make_deps(shell)
    assert quickstart.main(["--yes"], deps=deps, root=root) == 0
    pulled = {c[2] for c in shell.ran if c[:2] == ["ollama", "pull"]}
    assert pulled == MODELS
    assert any("crawl" in c for c in shell.ran)
    cmd, env = shell.spawned[0]
    assert cmd[-2:] == ["scripts/dev_cpu.py", "--show-credentials"]
    token = env[quickstart.QR_ENV]
    assert len(token) >= 16 and env["PATH"] == "x"
    (url,) = deps.opened  # type: ignore[attr-defined]
    assert url.endswith(f"/?lop={token}#hoi-thu-tuc")
    assert f":{APP['ports']['web']}/" in url
    assert shell.proc.waited


def test_ready_repo_skips_downloads_and_respects_no_browser(tmp_path: Path) -> None:
    shell = FakeShell()
    deps = make_deps(shell)
    root = make_root(tmp_path, with_index=True)
    assert quickstart.main(["--yes", "--no-browser"], deps=deps, root=root) == 0
    assert not any(c[:2] == ["ollama", "pull"] for c in shell.ran)
    assert not any("crawl" in c for c in shell.ran)
    assert deps.opened == []  # type: ignore[attr-defined]


def test_existing_token_is_reused(tmp_path: Path) -> None:
    shell = FakeShell()
    deps = make_deps(shell)
    deps.environ = {"PATH": "x", quickstart.QR_ENV: "preset-token-123456"}
    quickstart.main(["--yes"], deps=deps, root=make_root(tmp_path, with_index=True))
    assert shell.spawned[0][1][quickstart.QR_ENV] == "preset-token-123456"


def test_failed_step_stops_the_run(tmp_path: Path, capsys) -> None:
    shell = FakeShell(fail_on="pnpm install")
    root = make_root(tmp_path, with_index=True)
    code = quickstart.main(["--yes"], deps=make_deps(shell), root=root)
    assert code == 1
    assert shell.spawned == []
    assert "pnpm install" in capsys.readouterr().out


def test_pipeline_without_index_is_an_error(tmp_path: Path) -> None:
    shell = FakeShell()
    root = make_root(tmp_path, with_index=False)
    assert quickstart.main(["--yes"], deps=make_deps(shell), root=root) == 1
    assert shell.spawned == []


def test_demo_that_dies_early_returns_its_code_without_browser(tmp_path: Path) -> None:
    shell = FakeShell(proc=FakeProc(code=2, alive=False))
    deps = make_deps(shell, probe_ok=False)
    code = quickstart.main(["--yes"], deps=deps, root=make_root(tmp_path, with_index=True))
    assert code == 2
    assert deps.opened == []  # type: ignore[attr-defined]


def test_demo_that_never_answers_times_out_without_browser(tmp_path: Path, capsys) -> None:
    shell = FakeShell(proc=FakeProc(code=0, alive=True))
    deps = make_deps(shell, probe_ok=False)
    code = quickstart.main(["--yes"], deps=deps, root=make_root(tmp_path, with_index=True))
    assert code == 0
    assert deps.opened == []  # type: ignore[attr-defined]
    assert "log" in capsys.readouterr().out.lower()
