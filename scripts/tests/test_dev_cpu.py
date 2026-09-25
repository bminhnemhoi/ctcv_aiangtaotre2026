from __future__ import annotations

import json
from pathlib import Path

import dev_cpu
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
APP = yaml.safe_load((ROOT / "config" / "app.yaml").read_text(encoding="utf-8"))
RAG = yaml.safe_load((ROOT / "config" / "rag.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ config and arguments
def test_load_config_reads_ports_and_models_from_config() -> None:
    cfg = dev_cpu.load_config(ROOT)
    assert cfg.api_port == APP["ports"]["api"]
    assert cfg.web_port == APP["ports"]["web"]
    assert cfg.ollama_default == RAG["serving"]["endpoint"]
    assert cfg.ollama_env == RAG["serving"]["endpoint_env"]
    assert set(cfg.required_models) == {
        RAG["embed"]["serving_name"],
        RAG["compose"]["serving_name"],
    }
    assert cfg.index_meta == ROOT / RAG["kb"]["index_dir"] / "index_meta.json"
    assert cfg.staff_username == RAG["demo"]["staff_username"]


def test_parse_args_defaults() -> None:
    args = dev_cpu.parse_args([])
    assert args.show_credentials is False
    assert args.run == []
    assert args.no_warmup is False


def test_parse_args_run_takes_the_rest_of_the_line() -> None:
    args = dev_cpu.parse_args(["--show-credentials", "--run", "uv", "run", "pytest", "-q"])
    assert args.show_credentials is True
    assert args.run == ["uv", "run", "pytest", "-q"]


# ------------------------------------------------------------------ environment
def _cfg() -> dev_cpu.DemoConfig:
    return dev_cpu.load_config(ROOT)


def test_build_env_generates_temporary_secrets_when_missing() -> None:
    cfg = _cfg()
    env, generated = dev_cpu.build_env({"PATH": "x"}, cfg)
    assert len(env["CTCV_DEMO_QR_TOKEN"]) >= 16
    assert len(env["CTCV_DEMO_STAFF_PASSWORD"]) >= 12
    assert env["CTCV_DEMO_QR_TOKEN"] != env["CTCV_DEMO_STAFF_PASSWORD"]
    assert set(generated) >= {"CTCV_DEMO_QR_TOKEN", "CTCV_DEMO_STAFF_PASSWORD"}
    assert env[cfg.ollama_env] == cfg.ollama_default
    assert env["API_HOST"] == dev_cpu.LOOPBACK
    assert env["API_PORT"] == str(cfg.api_port)
    assert env["PATH"] == "x"


def test_build_env_gives_fresh_secrets_each_run() -> None:
    first, _ = dev_cpu.build_env({}, _cfg())
    second, _ = dev_cpu.build_env({}, _cfg())
    assert first["CTCV_DEMO_QR_TOKEN"] != second["CTCV_DEMO_QR_TOKEN"]


def test_build_env_keeps_values_already_set() -> None:
    cfg = _cfg()
    base = {
        "CTCV_DEMO_QR_TOKEN": "t" * 20,
        "CTCV_DEMO_STAFF_PASSWORD": "p" * 14,
        cfg.ollama_env: "http://127.0.0.1:9999",
    }
    env, generated = dev_cpu.build_env(base, cfg)
    assert env["CTCV_DEMO_QR_TOKEN"] == "t" * 20
    assert env["CTCV_DEMO_STAFF_PASSWORD"] == "p" * 14
    assert env[cfg.ollama_env] == "http://127.0.0.1:9999"
    assert "CTCV_DEMO_QR_TOKEN" not in generated


def test_build_env_refuses_prod() -> None:
    with pytest.raises(dev_cpu.DemoError):
        dev_cpu.build_env({"CTCV_ENV": "prod"}, _cfg())


# ------------------------------------------------------------------ checks
def test_missing_models_accepts_latest_suffix() -> None:
    tags = {"models": [{"name": "bge-m3:latest"}, {"name": "qwen3.5:2b"}]}
    assert dev_cpu.missing_models(tags, ["bge-m3", "qwen3.5:2b"]) == []


def test_missing_models_reports_absent_model() -> None:
    tags = {"models": [{"name": "bge-m3:latest"}]}
    assert dev_cpu.missing_models(tags, ["bge-m3", "qwen3.5:2b"]) == ["qwen3.5:2b"]


def test_check_ollama_unreachable_raises() -> None:
    def boom(url: str, timeout: float) -> dict:
        raise OSError("refused")

    with pytest.raises(dev_cpu.DemoError, match="Ollama"):
        dev_cpu.check_ollama("http://127.0.0.1:1", ["bge-m3"], fetch=boom)


def test_check_index_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(dev_cpu.DemoError, match="chunk_embed"):
        dev_cpu.check_index(tmp_path / "index_meta.json")


def test_check_index_present(tmp_path: Path) -> None:
    meta = tmp_path / "index_meta.json"
    meta.write_text(json.dumps({"n_chunks": 3, "records": 2}), encoding="utf-8")
    assert dev_cpu.check_index(meta) == {"n_chunks": 3, "records": 2}


# ------------------------------------------------------------------ health loop
class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_wait_for_health_succeeds_after_retries() -> None:
    clock = FakeClock()
    calls: list[str] = []

    def probe(url: str) -> bool:
        calls.append(url)
        return len(calls) >= 3

    ok = dev_cpu.wait_for(
        "http://h/v1/health", timeout=30, probe=probe, clock=clock.time, sleep=clock.sleep
    )
    assert ok is True
    assert len(calls) == 3


def test_wait_for_health_times_out() -> None:
    clock = FakeClock()
    ok = dev_cpu.wait_for(
        "http://h/v1/health",
        timeout=5,
        probe=lambda url: False,
        clock=clock.time,
        sleep=clock.sleep,
    )
    assert ok is False
    assert clock.now >= 5


def test_wait_for_stops_when_a_process_died() -> None:
    clock = FakeClock()
    ok = dev_cpu.wait_for(
        "http://h",
        timeout=30,
        probe=lambda url: False,
        clock=clock.time,
        sleep=clock.sleep,
        alive=lambda: False,
    )
    assert ok is False
    assert clock.now < 30


# ------------------------------------------------------------------ warm-up
def test_warm_up_joins_then_asks_with_bearer() -> None:
    sent: list[tuple[str, dict, dict]] = []

    def post(url: str, body: dict, headers: dict, timeout: float) -> tuple[int, dict]:
        sent.append((url, body, headers))
        if url.endswith("/v1/auth/join"):
            return 200, {"token": "jwt-abc"}
        return 200, {"answer": "x", "reason": "ok"}

    status = dev_cpu.warm_up("http://127.0.0.1:1", "q" * 20, post=post)
    assert status == 200
    assert sent[0][0].endswith("/v1/auth/join")
    assert sent[0][1]["qr_token"] == "q" * 20
    assert sent[1][0].endswith("/v1/coach/ask")
    assert sent[1][2]["Authorization"] == "Bearer jwt-abc"


def test_warm_up_timeout_follows_the_serving_timeout_of_the_config() -> None:
    # Reviewer 25/9: WARMUP_MARGIN_S and serving_timeout_s were unused (180 s hard-coded).
    cfg = dev_cpu.load_config(dev_cpu.ROOT)
    assert dev_cpu.warmup_timeout(cfg) == cfg.serving_timeout_s + dev_cpu.WARMUP_MARGIN_S


def test_warm_up_join_failure_raises() -> None:
    def post(url: str, body: dict, headers: dict, timeout: float) -> tuple[int, dict]:
        return 501, {"error": {"code": "NOT_IMPLEMENTED"}}

    with pytest.raises(dev_cpu.DemoError):
        dev_cpu.warm_up("http://127.0.0.1:1", "q" * 20, post=post)


# ------------------------------------------------------------------ banner and main
def _secrets(env: dict[str, str]) -> list[str]:
    return [env["CTCV_DEMO_QR_TOKEN"], env["CTCV_DEMO_STAFF_PASSWORD"], env["JWT_SECRET"]]


def test_banner_hides_secrets_by_default() -> None:
    cfg = _cfg()
    env, _ = dev_cpu.build_env({}, cfg)
    text = dev_cpu.banner(cfg, env, show_credentials=False)
    assert f":{cfg.web_port}/#hoi-thu-tuc" in text
    assert "#can-bo" in text
    for secret in _secrets(env):
        assert secret not in text


def test_banner_shows_credentials_only_when_asked() -> None:
    cfg = _cfg()
    env, _ = dev_cpu.build_env({}, cfg)
    text = dev_cpu.banner(cfg, env, show_credentials=True)
    assert env["CTCV_DEMO_QR_TOKEN"] in text
    assert env["CTCV_DEMO_STAFF_PASSWORD"] in text
    assert cfg.staff_username in text
    assert env["JWT_SECRET"] not in text


class FakeStack:
    def __init__(self) -> None:
        self.stopped = False
        self.env: dict[str, str] = {}

    def alive(self) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True


def _patch_main(monkeypatch: pytest.MonkeyPatch, stack: FakeStack, ran: list) -> None:
    def fake_start(cfg: dev_cpu.DemoConfig, env: dict, *, web: bool) -> FakeStack:
        stack.env = env
        return stack

    def fake_run(cmd: list[str], env: dict) -> int:
        ran.append((cmd, env))
        return 7

    monkeypatch.setattr(dev_cpu, "check_ollama", lambda url, models: None)
    monkeypatch.setattr(dev_cpu, "check_index", lambda path: {"n_chunks": 1, "records": 1})
    monkeypatch.setattr(dev_cpu, "start_stack", fake_start)
    monkeypatch.setattr(dev_cpu, "wait_for", lambda url, timeout, **kw: True)
    # v2: warm_up also receives timeout= (config serving timeout + margin); same stub.
    monkeypatch.setattr(dev_cpu, "warm_up", lambda base, token, **kwargs: 200)
    monkeypatch.setattr(dev_cpu, "run_command", fake_run)
    for key in ("CTCV_DEMO_QR_TOKEN", "CTCV_DEMO_STAFF_PASSWORD", "JWT_SECRET", "CTCV_ENV"):
        monkeypatch.delenv(key, raising=False)


def test_main_run_mode_passes_env_stops_stack_and_hides_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stack, ran = FakeStack(), []
    _patch_main(monkeypatch, stack, ran)
    code = dev_cpu.main(["--run", "uv", "run", "python", "smoke.py"])
    out = capsys.readouterr()
    assert code == 7
    assert stack.stopped is True
    assert ran[0][0] == ["uv", "run", "python", "smoke.py"]
    assert ran[0][1]["CTCV_DEMO_QR_TOKEN"] == stack.env["CTCV_DEMO_QR_TOKEN"]
    for secret in _secrets(stack.env):
        assert secret not in out.out
        assert secret not in out.err


def test_main_show_credentials_prints_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stack, ran = FakeStack(), []
    _patch_main(monkeypatch, stack, ran)
    dev_cpu.main(["--show-credentials", "--run", "true"])
    assert stack.env["CTCV_DEMO_QR_TOKEN"] in capsys.readouterr().out


def test_main_reports_missing_index_without_starting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stack, ran = FakeStack(), []
    _patch_main(monkeypatch, stack, ran)

    def no_index(path: Path) -> dict:
        raise dev_cpu.DemoError("thiếu chỉ mục, chạy chunk_embed")

    monkeypatch.setattr(dev_cpu, "check_index", no_index)
    code = dev_cpu.main(["--run", "true"])
    assert code == 2
    assert ran == []
    assert "chunk_embed" in capsys.readouterr().err


def test_main_stops_stack_when_health_never_comes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stack, ran = FakeStack(), []
    _patch_main(monkeypatch, stack, ran)
    monkeypatch.setattr(dev_cpu, "wait_for", lambda url, timeout, **kw: False)
    code = dev_cpu.main(["--run", "true"])
    assert code == 3
    assert stack.stopped is True
    assert ran == []
