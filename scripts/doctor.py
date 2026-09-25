"""Environment doctor for CTCV (``make doctor``). Standard library only.

Prints a Vietnamese OK/WARN/FAIL/INFO table and exits 1 only when a *hard*
requirement fails: Python ≥ 3.12 (via uv), uv itself, the three source-of-truth
docs and the BTC dossier template. Everything else is advisory.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SPEC = ">=3.12,<3.13"
MIN_NODE_MAJOR = 20
MIN_PNPM_MAJOR = 10
REQUIRED_DOCS = ("docs/idea.md", "docs/plan.md", "docs/prompt.md")
TEMPLATE_DOCX = "docs/template/AI2026_Mau_ho_so.docx"
PLACEHOLDER_VALUES = {"", "CHANGE_ME"}
SKIP_DOMAINS = {"", "localhost", "127.0.0.1"}
VERSION_RE = re.compile(r"\d+\.\d+(?:\.\d+)?")
WINDOWS_MAKE_HINT = (
    "cài bằng `winget install ezwinports.make` rồi thêm "
    "%LOCALAPPDATA%\\Microsoft\\WinGet\\Links vào PATH (xem README)"
)

Runner = Callable[[list[str]], tuple[int, str]]


@dataclass(frozen=True)
class Check:
    """One diagnostic row."""

    status: str  # OK | WARN | FAIL | INFO
    name: str
    detail: str
    hard: bool = False


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    """Run ``cmd`` and return ``(returncode, combined output)``; never raises.

    The executable is resolved with ``shutil.which`` so ``.cmd`` shims such as
    ``pnpm.cmd`` are found on Windows (CreateProcess only appends ``.exe``).
    """
    resolved = shutil.which(cmd[0]) or cmd[0]
    try:
        proc = subprocess.run(
            [resolved, *cmd[1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return 127, "không tìm thấy lệnh"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 124, f"lỗi khi chạy: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _version_of(output: str) -> str | None:
    match = VERSION_RE.search(output)
    return match.group(0) if match else None


def _major(version: str | None) -> int:
    return int(version.split(".")[0]) if version else -1


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (values are never printed by this script)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def check_uv(run: Runner) -> Check:
    """Uv is a hard requirement."""
    code, out = run(["uv", "--version"])
    if code != 0:
        return Check("FAIL", "uv", "chưa cài uv (https://docs.astral.sh/uv/)", hard=True)
    return Check("OK", "uv", out.splitlines()[0])


def check_python(run: Runner) -> Check:
    """Python 3.12 must be resolvable by uv (falls back to the running interpreter)."""
    code, out = run(["uv", "python", "find", PYTHON_SPEC])
    if code == 0 and out:
        return Check("OK", "Python 3.12", out.splitlines()[-1])
    if sys.version_info[:2] == (3, 12):
        return Check(
            "OK", "Python 3.12", f"đang chạy {platform.python_version()} (uv chưa tìm thấy)"
        )
    return Check(
        "FAIL",
        "Python 3.12",
        f"uv không tìm thấy Python {PYTHON_SPEC}: chạy `uv python install 3.12`",
        hard=True,
    )


def check_versioned_tool(run: Runner, name: str, min_major: int, hint: str) -> Check:
    """Advisory check for node/pnpm-style tools with a minimum major version."""
    code, out = run([name, "--version"])
    version = _version_of(out) if code == 0 else None
    if version is None:
        return Check("WARN", name, f"chưa có {name} — {hint}")
    if _major(version) < min_major:
        return Check("WARN", name, f"phiên bản {version} < {min_major} — {hint}")
    return Check("OK", name, version)


def check_simple_tool(
    run: Runner, name: str, hint: str, args: tuple[str, ...] = ("--version",)
) -> Check:
    """Advisory presence check."""
    code, out = run([name, *args])
    if code != 0:
        return Check("WARN", name, f"chưa có {name} — {hint}")
    return Check("OK", name, (out.splitlines() or [""])[0][:60])


def check_docker(run: Runner) -> Check:
    """Docker daemon reachability (advisory on the dev machine)."""
    code, out = run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if code != 0:
        return Check(
            "WARN",
            "Docker",
            "daemon không phản hồi — mở Docker Desktop hoặc `sudo systemctl start docker`",
        )
    return Check("OK", "Docker", f"daemon {out.splitlines()[-1] if out else 'sẵn sàng'}")


def check_make(run: Runner) -> Check:
    """Make presence, with the winget hint on Windows."""
    code, out = run(["make", "--version"])
    if code == 0:
        return Check("OK", "make", (out.splitlines() or [""])[0])
    hint = (
        WINDOWS_MAKE_HINT if platform.system() == "Windows" else "cài gói `make` của hệ điều hành"
    )
    return Check("WARN", "make", f"chưa có make — {hint}")


def check_env_file(root: Path) -> Check:
    """Compare .env against .env.example keys without revealing values."""
    example = parse_env_file(root / ".env.example")
    if not example:
        return Check("WARN", ".env", "thiếu .env.example — không kiểm tra được")
    if not (root / ".env").is_file():
        return Check("WARN", ".env", "chưa có .env — `cp .env.example .env` rồi điền giá trị")
    missing = sorted(set(example) - set(parse_env_file(root / ".env")))
    if missing:
        return Check("WARN", ".env", f"thiếu {len(missing)} biến: {', '.join(missing)}")
    return Check("OK", ".env", f"đủ {len(example)} biến so với .env.example")


def check_required_files(root: Path) -> list[Check]:
    """Source-of-truth docs and the BTC template are hard requirements."""
    checks = []
    for rel in (*REQUIRED_DOCS, TEMPLATE_DOCX):
        exists = (root / rel).is_file()
        checks.append(
            Check(
                "OK" if exists else "FAIL",
                rel,
                "có mặt" if exists else "THIẾU — không thể sinh hồ sơ",
                hard=True,
            )
        )
    return checks


def check_git(run: Runner, root: Path) -> Check:
    """Git repo present and identity configured (advisory)."""
    code, _ = run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"])
    if code != 0:
        return Check("WARN", "git", "thư mục chưa là kho git — `git init -b main`")
    _, name = run(["git", "-C", str(root), "config", "user.name"])
    _, email = run(["git", "-C", str(root), "config", "user.email"])
    if not name.strip() or not email.strip():
        return Check("WARN", "git", "chưa đặt user.name/user.email — `git config user.name ...`")
    return Check("OK", "git", f"kho git, tác giả {name.strip()}")


def check_hf_token(root: Path) -> Check:
    """HF_TOKEN present in the environment or .env (value never printed)."""
    value = os.environ.get("HF_TOKEN") or parse_env_file(root / ".env").get("HF_TOKEN", "")
    if value.strip() in PLACEHOLDER_VALUES:
        return Check("WARN", "HF_TOKEN", "chưa đặt — cần khi tải model có cổng (Qwen, PhoWhisper)")
    return Check("OK", "HF_TOKEN", "đã đặt")


def check_gpu(run: Runner) -> Check:
    """GPU information only (dev machine has none; training runs elsewhere)."""
    code, out = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if code != 0 or not out:
        return Check(
            "INFO", "GPU", "không có NVIDIA GPU — train/eval đầy đủ chạy trên máy GPU thuê"
        )
    return Check("INFO", "GPU", out.splitlines()[0])


def check_dns(root: Path, resolve: Callable[[str], str] = socket.gethostbyname) -> Check:
    """Resolve APP_DOMAIN when configured (information only)."""
    domain = os.environ.get("APP_DOMAIN") or parse_env_file(root / ".env").get("APP_DOMAIN", "")
    if domain.strip() in SKIP_DOMAINS or domain.strip() in PLACEHOLDER_VALUES:
        return Check("INFO", "DNS", "APP_DOMAIN chưa đặt hoặc là localhost — bỏ qua")
    try:
        address = resolve(domain)
    except OSError:
        return Check("INFO", "DNS", f"{domain} chưa phân giải được — kiểm tra bản ghi A/CNAME")
    return Check("INFO", "DNS", f"{domain} → {address}")


def check_gpu_host(run: Runner, root: Path) -> list[Check]:
    """`make doctor GPU=1` (D29): reach the rented GPU machine over SSH and read nvidia-smi."""
    host = os.environ.get("GPU_SSH_HOST") or parse_env_file(root / ".env").get("GPU_SSH_HOST", "")
    if host.strip() in PLACEHOLDER_VALUES:
        return [
            Check(
                "WARN", "GPU host", "GPU_SSH_HOST chưa đặt trong .env — không kiểm tra được máy GPU"
            )
        ]
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host]
    code, out = run([*ssh, "nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if code != 0:
        return [
            Check(
                "WARN",
                "GPU host",
                f"không SSH/nvidia-smi được tới {host} — kiểm tra khóa SSH và driver",
            )
        ]
    rows = [Check("OK", "GPU host", f"{host}: {out.splitlines()[0]}")]
    code, out = run([*ssh, "docker", "--version"])
    rows.append(
        Check(
            "OK" if code == 0 else "WARN",
            "GPU docker",
            out.splitlines()[0] if code == 0 else f"docker chưa có trên {host}",
        )
    )
    return rows


def run_all(root: Path, run: Runner = run_command, gpu: bool = False) -> list[Check]:
    """Run every check and return the rows in display order."""
    return [
        check_uv(run),
        check_python(run),
        check_versioned_tool(run, "node", MIN_NODE_MAJOR, "cài Node 20+ (https://nodejs.org)"),
        check_versioned_tool(run, "pnpm", MIN_PNPM_MAJOR, "`corepack enable` hoặc `npm i -g pnpm`"),
        check_docker(run),
        check_make(run),
        check_simple_tool(
            run,
            "gitleaks",
            "quét secret bị bỏ qua khi thiếu (`winget install Gitleaks.Gitleaks`)",
            ("version",),
        ),
        check_simple_tool(run, "ruff", "`uv tool install ruff`"),
        check_simple_tool(run, "pre-commit", "`uv tool install pre-commit`"),
        check_env_file(root),
        *check_required_files(root),
        check_git(run, root),
        check_hf_token(root),
        check_gpu(run),
        check_dns(root),
        *(check_gpu_host(run, root) if gpu else []),
    ]


def render(checks: list[Check]) -> str:
    """Render the table."""
    width = max(len(c.name) for c in checks)
    lines = [f"{'TRẠNG THÁI':<10} {'HẠNG MỤC':<{width}}  CHI TIẾT", "-" * (width + 40)]
    lines += [f"{c.status:<10} {c.name:<{width}}  {c.detail}" for c in checks]
    return "\n".join(lines)


def hard_failures(checks: list[Check]) -> list[Check]:
    """Rows that make the doctor exit non-zero."""
    return [c for c in checks if c.status == "FAIL" and c.hard]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--gpu", action="store_true", help="kiểm tra thêm máy GPU qua SSH (GPU_SSH_HOST)"
    )
    args = parser.parse_args(argv)
    checks = run_all(args.root, gpu=args.gpu)
    print(render(checks))
    failures = hard_failures(checks)
    warns = sum(1 for c in checks if c.status == "WARN")
    if failures:
        print(
            f"\nDOCTOR: {len(failures)} yêu cầu bắt buộc chưa đạt — sửa trước khi `make install`."
        )
        return 1
    print(f"\nDOCTOR OK: đủ yêu cầu bắt buộc; {warns} cảnh báo nên xử lý.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
