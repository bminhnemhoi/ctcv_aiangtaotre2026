"""One command to try CTCV locally: check tools, fetch models and data, start the demo, open it.

Usage (Git Bash / any terminal, repo root)::

    uv run python scripts/quickstart.py              # everything; asks once before downloading
    uv run python scripts/quickstart.py --check      # only check and print the plan; runs nothing
    uv run python scripts/quickstart.py --yes        # do not ask for confirmation
    uv run python scripts/quickstart.py --no-data    # never crawl (the index must already exist)
    uv run python scripts/quickstart.py --no-browser # do not open the browser

Steps: (1) check ``uv``, ``node``, ``pnpm`` and ``ollama`` (minimum versions from ``package.json``
``engines``) and print install instructions when one is missing — system software is never
installed by this script; (2) ``ollama pull`` the embed and compose models of ``config/rag.yaml``
that Ollama does not have yet; (3) ``uv sync --all-packages`` and ``pnpm install
--frozen-lockfile``; (4) when the TTHC index of ``config/rag.yaml`` is missing, build it from the
public pages of the portal (``crawl --online``, ``normalize``, ``chunk_embed --online`` of
``ctcv_data.pipeline``; robots.txt and the pacing of ``data/sources.yaml`` are respected);
(5) run ``scripts/dev_cpu.py --show-credentials`` and open the citizen page once web and API answer.
Exit codes: 0 ok, 1 a step failed or was declined, 2 a precondition is missing, 3 demo not up.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("uv", "node", "pnpm", "ollama")
VERSIONED = ("node", "pnpm")
DEV_CPU = "scripts/dev_cpu.py"
QR_ENV = "CTCV_DEMO_QR_TOKEN"
SECRET_BYTES = 24
STARTUP_TIMEOUT_S = 300.0
POLL_S = 1.0
STOP_WAIT_S = 30.0
PIPELINE = ("uv", "run", "python", "-m", "ctcv_data.pipeline")
INSTALL_HINTS = {
    "uv": "Windows: winget install --id astral-sh.uv -e · macOS/Linux: "
    "https://docs.astral.sh/uv/getting-started/installation/",
    "node": "Node.js >= {node} — Windows: winget install OpenJS.NodeJS.LTS · "
    "khác: https://nodejs.org/en/download",
    "pnpm": "pnpm >= {pnpm} — corepack enable pnpm (đi kèm Node.js) hoặc npm install -g pnpm",
    "ollama": "Windows: winget install Ollama.Ollama · macOS/Linux: https://ollama.com/download",
}


class Proc(Protocol):
    """The subset of :class:`subprocess.Popen` the launcher uses."""

    def poll(self) -> int | None:
        """Exit code, or None while running."""
        ...

    def wait(self, timeout: float | None = None) -> int:
        """Block until the process exits."""
        ...


class Shell(Protocol):
    """Everything that touches the operating system; tests inject a fake."""

    def which(self, name: str) -> str | None:
        """Full path of ``name`` on PATH, or None."""
        ...

    def capture(self, cmd: Sequence[str]) -> tuple[int, str]:
        """Run ``cmd`` quietly and return ``(exit code, stdout)``."""
        ...

    def run(self, cmd: Sequence[str]) -> int:
        """Run ``cmd`` with output on the console and return its exit code."""
        ...

    def spawn(self, cmd: Sequence[str], env: dict[str, str]) -> Proc:
        """Start ``cmd`` in the background with ``env``."""
        ...


@dataclass
class RealShell:
    """Subprocess-backed :class:`Shell`; commands run in ``root`` (``.cmd`` shims resolved)."""

    root: Path = ROOT

    def which(self, name: str) -> str | None:
        """Full path of ``name`` on PATH, or None."""
        return shutil.which(name)

    def _argv(self, cmd: Sequence[str]) -> list[str]:
        return [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]

    def capture(self, cmd: Sequence[str]) -> tuple[int, str]:
        """Run ``cmd`` quietly and return ``(exit code, stdout)``."""
        try:
            done = subprocess.run(
                self._argv(cmd),
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 127, type(exc).__name__
        return done.returncode, done.stdout

    def run(self, cmd: Sequence[str]) -> int:
        """Run ``cmd`` with output on the console and return its exit code."""
        try:
            return subprocess.call(self._argv(cmd), cwd=self.root)
        except OSError:
            return 127

    def spawn(self, cmd: Sequence[str], env: dict[str, str]) -> Proc:
        """Start ``cmd`` in the background with ``env`` (same console, so Ctrl-C reaches it)."""
        return subprocess.Popen(self._argv(cmd), cwd=self.root, env=env)


@dataclass
class Deps:
    """Injectable side effects of :func:`main`."""

    shell: Shell
    probe: Callable[[str], bool]
    open_url: Callable[[str], bool]
    ask: Callable[[str], str]
    environ: Mapping[str, str]
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


def http_probe(url: str) -> bool:
    """``GET url`` answers 200 (``dev_cpu`` needs PyYAML, so it is imported lazily)."""
    import dev_cpu

    return dev_cpu.http_ok(url)


def default_deps(root: Path = ROOT) -> Deps:
    """Real shell, HTTP probe, system browser and console prompt."""
    return Deps(
        shell=RealShell(root),
        probe=http_probe,
        open_url=webbrowser.open,
        ask=input,
        environ=dict(os.environ),
    )


@dataclass(frozen=True)
class QuickConfig:
    """Values read from ``config/app.yaml``, ``config/rag.yaml``, ``package.json``, sources."""

    root: Path
    models: tuple[str, ...]
    index_meta: Path
    web_url: str
    health_url: str
    portal: str
    crawl_interval_s: float
    min_versions: dict[str, int] = field(default_factory=dict)


def load_config(root: Path = ROOT) -> QuickConfig:
    """Read models, ports, index path, portal name, crawl pacing and minimum tool versions."""
    import dev_cpu
    import yaml

    demo = dev_cpu.load_config(root)
    rag = yaml.safe_load((root / "config" / "rag.yaml").read_text(encoding="utf-8"))
    sources = yaml.safe_load((root / "data" / "sources.yaml").read_text(encoding="utf-8"))
    return QuickConfig(
        root=root,
        models=demo.required_models,
        index_meta=demo.index_meta,
        web_url=f"http://{dev_cpu.LOOPBACK}:{demo.web_port}/",
        health_url=f"http://{dev_cpu.LOOPBACK}:{demo.api_port}{dev_cpu.HEALTH_PATH}",
        portal=str(rag["kb"]["source_portal"]),
        crawl_interval_s=float(sources["crawl_rules"]["min_interval_s"]),
        min_versions=min_versions(root),
    )


def min_versions(root: Path = ROOT) -> dict[str, int]:
    """Minimum major versions of node and pnpm from ``package.json`` ``engines`` (stdlib only)."""
    try:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pkg = {}
    engines = pkg.get("engines", {})
    return {name: version_major(str(engines.get(name, ""))) or 0 for name in VERSIONED}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the four flags of the quickstart."""
    parser = argparse.ArgumentParser(description="Chạy thử CTCV bằng một lệnh (máy cục bộ).")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra, không chạy gì")
    parser.add_argument("--no-data", action="store_true", help="Không tải/tạo kho thủ tục")
    parser.add_argument("--no-browser", action="store_true", help="Không mở trình duyệt")
    parser.add_argument("--yes", action="store_true", help="Không hỏi xác nhận")
    return parser.parse_args(argv)


# ------------------------------------------------------------------ pure helpers
def version_major(text: str) -> int | None:
    """Major version in ``text`` (``v20.11.1`` → 20, ``>=10`` → 10), or None."""
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def parse_ollama_list(text: str) -> set[str]:
    """Model names of ``ollama list`` output; ``x:latest`` also yields ``x``."""
    names: set[str] = set()
    for line in text.splitlines()[1:]:
        if line.strip():
            name = line.split()[0]
            names |= {name, name.removesuffix(":latest")}
    return names


def missing_models(installed: set[str], required: Sequence[str]) -> list[str]:
    """Required models that Ollama does not have, in config order."""
    return [m for m in required if m not in installed]


def install_help(missing: Sequence[str], min_versions: Mapping[str, int]) -> str:
    """Install instructions for ``missing`` tools (links and package managers only)."""
    lines = ["Thiếu công cụ — cài rồi mở lại terminal và chạy lại lệnh này:"]
    for name in missing:
        lines.append(f"  - {name}: {INSTALL_HINTS[name].format(**min_versions)}")
    return "\n".join(lines)


@dataclass(frozen=True)
class Step:
    """One command of the plan, with an optional note printed before it runs."""

    label: str
    cmd: list[str]
    note: str = ""


def data_steps(cfg: QuickConfig) -> list[Step]:
    """Build the TTHC index from the public portal (crawl, normalize, chunk + embed)."""
    note = (
        f"Tải các trang thủ tục CÔNG KHAI của {cfg.portal} — tôn trọng robots.txt, "
        f"mỗi yêu cầu cách nhau ≥ {cfg.crawl_interval_s:g} s; mất khoảng 3–5 phút. "
        "Dữ liệu chỉ lưu trên máy này (data/raw, data/clean), không phân phối lại."
    )
    return [
        Step("Tải trang thủ tục", [*PIPELINE, "crawl", "--online"], note),
        Step("Chuẩn hóa thủ tục", [*PIPELINE, "normalize"]),
        Step("Cắt đoạn + tạo chỉ mục", [*PIPELINE, "chunk_embed", "--online"]),
    ]


def build_plan(cfg: QuickConfig, absent: Sequence[str], *, with_data: bool) -> list[Step]:
    """Model pulls, dependency installs and (optionally) the data pipeline, in run order."""
    plan = [Step(f"Tải model {m}", ["ollama", "pull", m]) for m in absent]
    plan.append(Step("Cài thư viện Python", ["uv", "sync", "--all-packages"]))
    plan.append(Step("Cài thư viện web", ["pnpm", "install", "--frozen-lockfile"]))
    return plan + (data_steps(cfg) if with_data else [])


def citizen_url(cfg: QuickConfig, token: str) -> str:
    """Citizen page with the class token (same link ``dev_cpu --show-credentials`` prints)."""
    return f"{cfg.web_url}?lop={token}#hoi-thu-tuc"


def demo_env(base: Mapping[str, str]) -> dict[str, str]:
    """Environment for ``dev_cpu``; the class token is generated here so the URL is known."""
    env = dict(base)
    if not env.get(QR_ENV):
        env[QR_ENV] = secrets.token_urlsafe(SECRET_BYTES)
    env["PYTHONUTF8"] = "1"
    return env


# ------------------------------------------------------------------ checks
def check_tools(shell: Shell, mins: Mapping[str, int]) -> str | None:
    """Return install instructions when a tool is missing or older than ``mins``, else None."""
    missing = [t for t in TOOLS if shell.which(t) is None]
    if missing:
        return install_help(missing, mins)
    old = []
    for name in VERSIONED:
        code, out = shell.capture([name, "--version"])
        major = version_major(out) if code == 0 else None
        if major is None or major < mins.get(name, 0):
            old.append(name)
    return install_help(old, mins) if old else None


def ollama_models(shell: Shell) -> set[str] | None:
    """Installed Ollama models, or None when the Ollama server does not answer."""
    code, out = shell.capture(["ollama", "list"])
    return parse_ollama_list(out) if code == 0 else None


def index_ready(cfg: QuickConfig) -> bool:
    """True when the TTHC index metadata of ``config/rag.yaml`` exists."""
    return cfg.index_meta.is_file()


def print_plan(plan: Sequence[Step]) -> None:
    """Print the commands that would run."""
    print("Các bước sẽ chạy:" if plan else "Không cần cài thêm gì.")
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step.label}: {' '.join(step.cmd)}")


def confirm(ask: Callable[[str], str], yes: bool) -> bool:
    """Ask once before downloading; ``--yes`` skips the question, EOF means no."""
    if yes:
        return True
    try:
        answer = ask("Tiếp tục? [Y/n] ").strip().lower()
    except EOFError:
        return False
    return answer in ("", "y", "yes", "c", "co", "có")


def run_plan(shell: Shell, plan: Sequence[Step]) -> int:
    """Run every step in order; stop at the first failure and say which command failed."""
    for i, step in enumerate(plan, 1):
        print(f"\n[{i}/{len(plan)}] {step.label}", flush=True)
        if step.note:
            print(f"    {step.note}", flush=True)
        code = shell.run(step.cmd)
        if code != 0:
            print(f"LỖI (mã {code}) ở lệnh: {' '.join(step.cmd)} — sửa rồi chạy lại.", flush=True)
            return 1
    return 0


# ------------------------------------------------------------------ demo
def wait_until_up(cfg: QuickConfig, proc: Proc, deps: Deps) -> bool:
    """Poll web and API health until both answer, the demo exits or the timeout elapses."""
    deadline = deps.clock() + STARTUP_TIMEOUT_S
    while proc.poll() is None and deps.clock() < deadline:
        if deps.probe(cfg.health_url) and deps.probe(cfg.web_url):
            return True
        deps.sleep(POLL_S)
    return False


def launch_demo(cfg: QuickConfig, args: argparse.Namespace, deps: Deps) -> int:
    """Run ``dev_cpu`` in the foreground console and open the citizen page when it is up."""
    env = demo_env(deps.environ)
    proc = deps.shell.spawn(["uv", "run", "python", DEV_CPU, "--show-credentials"], env)
    try:
        if wait_until_up(cfg, proc, deps):
            if not args.no_browser:
                print("Mở trình duyệt tới trang người dân (#hoi-thu-tuc)...", flush=True)
                deps.open_url(citizen_url(cfg, env[QR_ENV]))
        elif proc.poll() is not None:
            return proc.poll() or 3
        else:
            print("Demo chưa trả lời sau thời gian chờ; xem log dev_cpu ở trên.", flush=True)
        return proc.wait()
    except KeyboardInterrupt:
        print("Đang dừng demo...", flush=True)
        try:
            proc.wait(timeout=STOP_WAIT_S)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            pass
        return 130


# ------------------------------------------------------------------ main
def prepare(shell: Shell, root: Path) -> QuickConfig | None:
    """Check tools, then read the config; print why and return None when not ready."""
    error = check_tools(shell, min_versions(root))
    if error:
        print(error)
        return None
    try:
        return load_config(root)
    except ImportError:
        print("Chạy bằng: uv run python scripts/quickstart.py (uv tự cài PyYAML).")
        return None


def main(argv: list[str] | None = None, *, deps: Deps | None = None, root: Path = ROOT) -> int:
    """Entry point (see the module docstring for steps and exit codes)."""
    _utf8_stdout()
    args = parse_args(argv)
    deps = deps or default_deps(root)
    cfg = prepare(deps.shell, root)
    if cfg is None:
        return 2
    installed = ollama_models(deps.shell)
    if installed is None:
        print("Ollama chưa chạy: mở ứng dụng Ollama (hoặc chạy `ollama serve`) rồi chạy lại.")
        return 2
    has_index = index_ready(cfg)
    absent = missing_models(installed, cfg.models)
    plan = build_plan(cfg, absent, with_data=not has_index and not args.no_data)
    print_plan(plan)
    if args.check:
        print("Kiểm tra xong: đủ công cụ. Bỏ --check để chạy các bước trên.")
        return 0
    if args.no_data and not has_index:
        print(f"Chưa có chỉ mục {cfg.index_meta}; bỏ --no-data để tạo (crawl, chunk_embed).")
        return 2
    if plan and not confirm(deps.ask, args.yes):
        print("Đã hủy; chưa chạy bước nào.")
        return 1
    if run_plan(deps.shell, plan) != 0:
        return 1
    if not index_ready(cfg):
        print(f"Pipeline chạy xong nhưng chưa có {cfg.index_meta}; xem thông báo ở trên.")
        return 1
    return launch_demo(cfg, args, deps)


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    sys.exit(main())
