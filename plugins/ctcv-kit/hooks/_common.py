"""Shared helpers for the CTCV Claude Code hooks.

Standard library only (brief D2): every hook is launched through
``.claude/hooks/run.sh`` outside the project virtualenv, on Windows Git Bash
and on Linux, with Python 3.10+. Nothing here imports ``ctcv_core`` on purpose.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

HOOKS_DIR = Path(__file__).resolve().parent
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
NO_GIT = "nogit"
CHUNK = 1 << 20
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
MASK = "[ĐÃ CHE:{kind}]"

# Secret-looking tokens (brief §11 prompt-guard). Order matters: specific first.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai/anthropic-key", re.compile(r"\bsk-(?:proj-|ant-(?:api\d+-)?)?[A-Za-z0-9_-]{16,}")),
    (
        "github-token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}"),
    ),
    ("huggingface-token", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    (
        "password=",
        re.compile(
            r"(?i)\bpass(?:word|wd)\s*[:=]\s*[\"']?"
            r"(?!(?:change_me|string|str|null|none|your\w*|x{3,}|\*+|\.{3})(?=\s|$|[\"']))"
            r"(?![<$\{])\S{4,}"
        ),
    ),
    (
        "key/secret/token≥40",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|key)\b[^\n]{0,20}?[:=]\s*[\"']?[A-Za-z0-9+/=_-]{40,}"
        ),
    ),
)


def utf8_streams() -> None:
    """Force UTF-8 on stdout/stderr so Vietnamese messages survive Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def now_iso() -> str:
    """Current UTC time, ISO-8601 with second precision."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def eprint(message: str) -> None:
    """Print one line to stderr (never raises)."""
    try:
        print(message, file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


def block(reason: str) -> NoReturn:
    """Print a Vietnamese reason to stderr and exit 2 (Claude Code blocks the action)."""
    eprint(f"Chặn (hook): {reason}")
    sys.exit(2)


def read_stdin_json() -> tuple[dict[str, Any] | None, str | None]:
    """Read the hook payload from stdin.

    Returns ``(data, None)`` on success and ``(None, reason)`` when stdin is a
    terminal, empty or not a JSON object. Callers decide whether that is fatal.
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return None, "stdin là terminal, không có dữ liệu hook"
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError) as exc:
        return None, f"không đọc được stdin: {exc}"
    if not raw.strip():
        return None, "stdin rỗng"
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        return None, f"JSON không hợp lệ: {exc}"
    if not isinstance(data, dict):
        return None, "dữ liệu hook không phải object JSON"
    return data, None


def project_dir(data: dict[str, Any] | None = None) -> Path:
    """Repository root: ``$CLAUDE_PROJECT_DIR``, else the hook's ``cwd``, else two levels up."""
    env = os.environ.get(PROJECT_DIR_ENV)
    if env:
        return Path(env).expanduser().resolve()
    cwd = (data or {}).get("cwd")
    if isinstance(cwd, str) and cwd:
        return Path(cwd).expanduser().resolve()
    return HOOKS_DIR.parents[1]


def rel_to_project(path: str, root: Path) -> str | None:
    """POSIX path of ``path`` relative to ``root``; ``None`` when it lies outside."""
    candidate = Path(path.replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def safe_id(value: Any, fallback: str = "unknown") -> str:
    """Reduce an identifier to ``[A-Za-z0-9._-]`` so it is safe as a file name."""
    text = SAFE_ID_RE.sub("-", str(value or "")).strip("-.")
    return text or fallback


def git(args: list[str], cwd: Path, timeout: int = 15) -> tuple[int, str]:
    """Run ``git <args>`` in ``cwd``; return ``(returncode, stdout)``; never raises."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return result.returncode, result.stdout.strip()


def git_head_short(root: Path) -> str:
    """Short HEAD hash or ``"nogit"`` before the first commit / outside a repo."""
    code, out = git(["rev-parse", "--short", "HEAD"], root)
    return out if code == 0 and out else NO_GIT


def git_branch(root: Path) -> str:
    """Current branch name or ``"nogit"``."""
    code, out = git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    return out if code == 0 and out else NO_GIT


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file, streamed."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON line (UTF-8, non-ASCII preserved), creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def mask_secrets(text: str) -> tuple[str, list[str]]:
    """Replace secret-looking tokens by ``[ĐÃ CHE:<kind>]``; return ``(masked, kinds)``."""
    kinds: list[str] = []
    for kind, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            kinds.append(kind)
            text = pattern.sub(MASK.format(kind=kind), text)
    return text, kinds


def read_text(path: Path, limit: int | None = None) -> str:
    """Read a UTF-8 text file leniently; return ``""`` when missing."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:limit] if limit else text


def replace_section(text: str, heading: str, body_lines: list[str]) -> str | None:
    """Replace the body of the ``## <heading>`` section; ``None`` when absent."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == f"## {heading}"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    new_lines = lines[: start + 1] + body_lines + [""] + lines[end:]
    return "\n".join(new_lines).rstrip("\n") + "\n"


def short(text: Any, limit: int) -> str:
    """First ``limit`` characters of ``text`` on one line."""
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"
