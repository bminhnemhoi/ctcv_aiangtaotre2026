"""PostToolUse formatter (brief D23): ``ruff format`` for ``.py``, prettier for web files.

Only formats — no ``--fix``, no pytest (tests run in ``make check`` / pre-commit).
Prettier runs only for ``.ts/.tsx/.css/.json`` under ``apps/`` and only when
``apps/web/node_modules`` exists. Failures are reported back to Claude through
``hookSpecificOutput.additionalContext``; the hook itself never blocks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _common import eprint, project_dir, read_stdin_json, rel_to_project, short, utf8_streams

PY_SUFFIXES = {".py"}
WEB_SUFFIXES = {".ts", ".tsx", ".css", ".json"}
WEB_PREFIX = "apps/"
NODE_MODULES = Path("apps") / "web" / "node_modules"
TIMEOUT = 60


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{cmd[0]}: {exc}"
    return result.returncode, (result.stdout + result.stderr).strip()


def ruff_command(root: Path) -> list[str] | None:
    """Prefer the project venv's ruff, then PATH, then ``uv run --no-sync``."""
    for candidate in (root / ".venv" / "Scripts" / "ruff.exe", root / ".venv" / "bin" / "ruff"):
        if candidate.is_file():
            return [str(candidate)]
    if shutil.which("ruff"):
        return ["ruff"]
    if shutil.which("uv"):
        return ["uv", "run", "--no-sync", "ruff"]
    return None


def prettier_command(root: Path) -> list[str] | None:
    """Local prettier binary (apps/web or root node_modules) or ``pnpm exec``."""
    names = ("prettier.cmd", "prettier") if os.name == "nt" else ("prettier",)
    for base in (root / NODE_MODULES, root / "node_modules"):
        for name in names:
            candidate = base / ".bin" / name
            if candidate.is_file():
                return [str(candidate)]
    if shutil.which("pnpm"):
        return ["pnpm", "-C", "apps/web", "exec", "prettier"]
    return None


def format_file(root: Path, rel: str) -> str | None:
    """Format one file; return an error message or ``None``."""
    suffix = Path(rel).suffix.lower()
    if suffix in PY_SUFFIXES:
        cmd = ruff_command(root)
        if cmd is None:
            return None
        code, out = _run([*cmd, "format", "--force-exclude", rel], root)
        return None if code == 0 else f"ruff format {rel} lỗi:\n{short(out, 800)}"
    if suffix in WEB_SUFFIXES and rel.startswith(WEB_PREFIX) and (root / NODE_MODULES).is_dir():
        cmd = prettier_command(root)
        if cmd is None:
            return None
        code, out = _run([*cmd, "--write", "--ignore-unknown", rel], root)
        return None if code == 0 else f"prettier {rel} lỗi:\n{short(out, 800)}"
    return None


def main() -> int:
    """Hook entry point; never blocks."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        eprint(f"format: dữ liệu hook không đọc được ({error}) — bỏ qua")
        return 0
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        return 0
    root = project_dir(data)
    rel = rel_to_project(raw, root)
    if rel is None or not (root / rel).is_file():
        return 0
    try:
        problem = format_file(root, rel)
    except Exception as exc:  # noqa: BLE001 — a formatter must never break the session
        problem = f"format hook lỗi không mong đợi: {exc}"
    if problem:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": problem,
                    }
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
