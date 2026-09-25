"""Run the CPU demo stack (API + web) against a local Ollama, localhost only (ADR-007 P9).

Usage (Git Bash, repo root)::

    uv run python scripts/dev_cpu.py                      # start, print URLs, Ctrl-C stops
    uv run python scripts/dev_cpu.py --show-credentials   # also print the temporary demo secrets
    uv run python scripts/dev_cpu.py --run uv run python my_smoke.py   # run a command, then stop

What it does: checks that Ollama serves the embed/compose models of ``config/rag.yaml`` and that
the TTHC index exists; generates temporary demo secrets (``CTCV_DEMO_QR_TOKEN``,
``CTCV_DEMO_STAFF_PASSWORD``, ``JWT_SECRET``) when they are not already in the environment;
starts ``uv run ctcv-api`` and the Vite dev server as child processes bound to 127.0.0.1 on the
ports of ``config/app.yaml``; waits for ``/v1/health``; warms the models up with one join + ask.
Secrets are never printed unless ``--show-credentials`` is given and never written to disk.
Child logs go to ``<tmp>/ctcv-dev-cpu/{api,web}.log``.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOOPBACK = "127.0.0.1"
HEALTH_PATH = "/v1/health"
WARMUP_QUESTION = "Đăng ký thường trú mất bao nhiêu tiền?"
WARMUP_NAME = "Học viên"
SECRET_BYTES = 24
DEFAULT_HEALTH_TIMEOUT_S = 120.0
WARMUP_MARGIN_S = 60.0
POLL_S = 1.0
LOG_DIR = Path(tempfile.gettempdir()) / "ctcv-dev-cpu"
SECRET_KEYS = ("CTCV_DEMO_QR_TOKEN", "CTCV_DEMO_STAFF_PASSWORD", "JWT_SECRET")

Fetch = Callable[[str, float], dict[str, Any]]
Post = Callable[[str, dict[str, Any], dict[str, str], float], tuple[int, dict[str, Any]]]


class DemoError(RuntimeError):
    """A precondition of the demo stack failed; the message is Vietnamese and actionable."""


@dataclass(frozen=True)
class DemoConfig:
    """Everything the launcher needs, read from ``config/app.yaml`` and ``config/rag.yaml``."""

    root: Path
    api_port: int
    web_port: int
    ollama_default: str
    ollama_env: str
    required_models: tuple[str, ...]
    index_meta: Path
    staff_username: str
    serving_timeout_s: float


def load_config(root: Path = ROOT) -> DemoConfig:
    """Read ports, Ollama endpoint, model names and index path from the repo config."""
    app = yaml.safe_load((root / "config" / "app.yaml").read_text(encoding="utf-8"))
    rag = yaml.safe_load((root / "config" / "rag.yaml").read_text(encoding="utf-8"))
    return DemoConfig(
        root=root,
        api_port=int(app["ports"]["api"]),
        web_port=int(app["ports"]["web"]),
        ollama_default=str(rag["serving"]["endpoint"]),
        ollama_env=str(rag["serving"]["endpoint_env"]),
        required_models=(str(rag["embed"]["serving_name"]), str(rag["compose"]["serving_name"])),
        index_meta=root / rag["kb"]["index_dir"] / "index_meta.json",
        staff_username=str(rag["demo"]["staff_username"]),
        serving_timeout_s=float(rag["serving"]["timeout_s"]),
    )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line; everything after ``--run`` is the command to execute."""
    parser = argparse.ArgumentParser(description="Chạy demo CTCV trên CPU (API + web, localhost).")
    parser.add_argument(
        "--show-credentials", action="store_true", help="In mã lớp và mật khẩu demo"
    )
    parser.add_argument("--no-web", action="store_true", help="Chỉ chạy API")
    parser.add_argument("--no-warmup", action="store_true", help="Bỏ bước nạp model")
    parser.add_argument("--timeout", type=float, default=DEFAULT_HEALTH_TIMEOUT_S)
    parser.add_argument("--run", nargs=argparse.REMAINDER, default=[], help="Lệnh chạy rồi dừng")
    return parser.parse_args(argv)


# ------------------------------------------------------------------ environment
def build_env(base: dict[str, str], cfg: DemoConfig) -> tuple[dict[str, str], list[str]]:
    """Return the child environment and the names of the secrets generated for this run."""
    if base.get("CTCV_ENV", "").strip().lower() == "prod":
        raise DemoError("CTCV_ENV=prod: không chạy chế độ demo ở môi trường prod.")
    env = dict(base)
    generated: list[str] = []
    for key in SECRET_KEYS:
        if not env.get(key):
            env[key] = secrets.token_urlsafe(SECRET_BYTES)
            generated.append(key)
    env.setdefault(cfg.ollama_env, cfg.ollama_default)
    env["API_HOST"] = LOOPBACK
    env["API_PORT"] = str(cfg.api_port)
    env["PYTHONUTF8"] = "1"
    return env, generated


# ------------------------------------------------------------------ HTTP helpers (no proxy)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    """GET ``url`` and decode its JSON body."""
    with _OPENER.open(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(
    url: str, body: dict[str, Any], headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, Any]]:
    """POST JSON and return ``(status, decoded body)``; HTTP errors are returned, not raised."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:200]}


def http_ok(url: str) -> bool:
    """Return True when ``GET url`` answers 200."""
    try:
        with _OPENER.open(url, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ------------------------------------------------------------------ preconditions
def missing_models(tags: dict[str, Any], required: list[str] | tuple[str, ...]) -> list[str]:
    """Return the required Ollama models absent from an ``/api/tags`` payload."""
    names = {str(m.get("name", "")) for m in tags.get("models", [])}
    names |= {n.removesuffix(":latest") for n in names}
    return [m for m in required if m not in names]


def check_ollama(base_url: str, models: tuple[str, ...] | list[str], fetch: Fetch = fetch_json):
    """Raise :class:`DemoError` unless Ollama at ``base_url`` serves every model in ``models``."""
    try:
        tags = fetch(base_url.rstrip("/") + "/api/tags", 10.0)
    except (OSError, ValueError) as exc:
        raise DemoError(
            f"Không gọi được Ollama ở {base_url} ({type(exc).__name__}). Mở Ollama rồi chạy lại."
        ) from exc
    absent = missing_models(tags, models)
    if absent:
        pulls = "; ".join(f"ollama pull {m}" for m in absent)
        raise DemoError(f"Ollama thiếu model: {', '.join(absent)}. Chạy: {pulls}")


def check_index(index_meta: Path) -> dict[str, Any]:
    """Return the index metadata or raise :class:`DemoError` with the command that builds it."""
    if not index_meta.is_file():
        raise DemoError(
            f"Chưa có chỉ mục {index_meta}. Chạy: "
            "uv run python -m ctcv_data.pipeline chunk_embed --online"
        )
    return json.loads(index_meta.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ processes
@dataclass
class Stack:
    """Child processes of the demo; :meth:`stop` kills each process tree."""

    procs: list[subprocess.Popen[bytes]] = field(default_factory=list)
    logs: list[Path] = field(default_factory=list)

    def alive(self) -> bool:
        """True while every child process is still running."""
        return all(p.poll() is None for p in self.procs)

    def stop(self) -> None:
        """Terminate every child process tree (idempotent)."""
        for proc in self.procs:
            if proc.poll() is None:
                _kill_tree(proc)
        self.procs.clear()


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _which(name: str, env: dict[str, str]) -> str:
    found = shutil.which(name, path=env.get("PATH"))
    if not found:
        raise DemoError(f"Không tìm thấy lệnh '{name}' trong PATH.")
    return found


def _spawn(cmd: list[str], env: dict[str, str], cwd: Path, log: Path) -> subprocess.Popen[bytes]:
    extra: dict[str, Any] = {}
    if os.name == "nt":
        extra["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        extra["start_new_session"] = True
    handle = log.open("wb")
    try:
        return subprocess.Popen(cmd, env=env, cwd=cwd, stdout=handle, stderr=handle, **extra)
    finally:
        handle.close()


def start_stack(cfg: DemoConfig, env: dict[str, str], *, web: bool) -> Stack:
    """Start the API (and the Vite dev server when ``web``) bound to 127.0.0.1."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stack = Stack()
    api_cmd = [_which("uv", env), "run", "ctcv-api"]
    stack.logs.append(LOG_DIR / "api.log")
    stack.procs.append(_spawn(api_cmd, env, cfg.root, stack.logs[-1]))
    if web:
        web_cmd = [_which("pnpm", env), "-C", "apps/web", "exec", "vite"]
        web_cmd += ["--host", LOOPBACK, "--port", str(cfg.web_port), "--strictPort"]
        stack.logs.append(LOG_DIR / "web.log")
        stack.procs.append(_spawn(web_cmd, env, cfg.root, stack.logs[-1]))
    return stack


def run_command(cmd: list[str], env: dict[str, str]) -> int:
    """Run ``cmd`` in the repo root with the demo environment and return its exit code."""
    return subprocess.call([_which(cmd[0], env), *cmd[1:]], env=env, cwd=ROOT)


# ------------------------------------------------------------------ waiting and warm-up
def wait_for(
    url: str,
    timeout: float,
    *,
    probe: Callable[[str], bool] = http_ok,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    alive: Callable[[], bool] = lambda: True,
) -> bool:
    """Poll ``url`` until it answers, ``timeout`` elapses or a child process dies."""
    deadline = clock() + timeout
    while True:
        if probe(url):
            return True
        if not alive() or clock() >= deadline:
            return False
        sleep(POLL_S)


def warmup_timeout(cfg: DemoConfig) -> float:
    """Model-server timeout of ``config/rag.yaml`` plus a margin for loading both models."""
    return cfg.serving_timeout_s + WARMUP_MARGIN_S


def warm_up(api_base: str, qr_token: str, post: Post = post_json, timeout: float = 180.0) -> int:
    """Join as the demo citizen and ask one question so both models are loaded."""
    status, body = post(
        api_base + "/v1/auth/join",
        {"qr_token": qr_token, "display_name": WARMUP_NAME},
        {},
        30.0,
    )
    if status != 200 or "token" not in body:
        raise DemoError(f"Warm-up: /v1/auth/join trả {status}.")
    headers = {"Authorization": f"Bearer {body['token']}"}
    status, _ = post(api_base + "/v1/coach/ask", {"question": WARMUP_QUESTION}, headers, timeout)
    return status


# ------------------------------------------------------------------ output
def banner(cfg: DemoConfig, env: dict[str, str], *, show_credentials: bool) -> str:
    """Human-readable URLs; secrets appear only when ``show_credentials`` is True."""
    web = f"http://{LOOPBACK}:{cfg.web_port}"
    lines = [
        f"Demo CTCV (CPU) sẵn sàng — chỉ nghe {LOOPBACK}; bí mật demo chỉ dùng cho lượt này.",
        f"  Người dân : {web}/#hoi-thu-tuc",
        f"  Cán bộ    : {web}/#can-bo  (tài khoản {cfg.staff_username})",
        f"  API       : http://{LOOPBACK}:{cfg.api_port}{HEALTH_PATH}",
        f"  Log       : {LOG_DIR}",
    ]
    if show_credentials:
        lines += [
            f"  Vào lớp   : {web}/?lop={env['CTCV_DEMO_QR_TOKEN']}#hoi-thu-tuc",
            f"  Mật khẩu cán bộ: {env['CTCV_DEMO_STAFF_PASSWORD']}",
        ]
    else:
        lines.append("  Mã lớp và mật khẩu cán bộ: thêm --show-credentials để in ra.")
    return "\n".join(lines)


def _tail(path: Path, n: int = 20) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------ main
def _serve(args: argparse.Namespace, cfg: DemoConfig, env: dict[str, str], stack: Any) -> int:
    api_base = f"http://{LOOPBACK}:{cfg.api_port}"
    if not wait_for(api_base + HEALTH_PATH, timeout=args.timeout, alive=stack.alive):
        print(f"LỖI: API không lên {HEALTH_PATH} trong {args.timeout:.0f} s.", file=sys.stderr)
        for log in getattr(stack, "logs", []):
            print(f"--- {log}\n{_tail(log)}", file=sys.stderr)
        return 3
    web_url = f"http://{LOOPBACK}:{cfg.web_port}/"
    if not args.no_web and not wait_for(web_url, timeout=args.timeout, alive=stack.alive):
        print(f"LỖI: web không lên ở {web_url}.", file=sys.stderr)
        return 3
    if not args.no_warmup:
        print("Đang nạp model (lượt hỏi đầu tiên)...", flush=True)
        status = warm_up(api_base, env["CTCV_DEMO_QR_TOKEN"], timeout=warmup_timeout(cfg))
        print(f"Warm-up /v1/coach/ask: HTTP {status}", flush=True)
    print(banner(cfg, env, show_credentials=args.show_credentials), flush=True)
    if args.run:
        return run_command(args.run, env)
    print("Bấm Ctrl-C để dừng.", flush=True)
    while stack.alive():
        time.sleep(POLL_S)
    print("Một tiến trình con đã dừng; xem log ở trên.", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns 2 for failed preconditions, 3 when the stack does not come up."""
    _utf8_stdout()
    args = parse_args(argv)
    cfg = load_config(ROOT)
    try:
        env, generated = build_env(dict(os.environ), cfg)
        check_index(cfg.index_meta)
        check_ollama(env[cfg.ollama_env], cfg.required_models)
    except DemoError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 2
    if generated:
        print(f"Đã sinh bí mật tạm cho lượt chạy này: {', '.join(generated)}", flush=True)
    try:
        stack = start_stack(cfg, env, web=not args.no_web)
    except DemoError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 2
    try:
        return _serve(args, cfg, env, stack)
    except DemoError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("Đang dừng demo...", flush=True)
        return 130
    finally:
        stack.stop()


if __name__ == "__main__":
    sys.exit(main())
