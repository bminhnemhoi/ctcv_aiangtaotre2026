"""PreToolUse guard for Edit/MultiEdit/Write/NotebookEdit (brief §11, D22) — fails CLOSED.

Blocks writes to: ``docs/prompt-log/**`` (hooks only), ``data/registry/*.lock``,
``docs/dossier/private/**`` (humans only), merged Alembic migrations (present on
``main``), ``config/eval.yaml`` (unless ``CTCV_ALLOW_EVAL_THRESHOLD=1`` or the
file is not on ``main`` yet) and the Claude Code / CI configuration
(``.claude/**``, ``CLAUDE.md``, ``.github/workflows/**``, ``.pre-commit-config.yaml``,
``Makefile``) unless the bootstrap marker ``.claude/BOOTSTRAP`` exists.
``eval/redteam/**`` and ``docs/security/**`` are always writable (security-redteam).
"""

from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path

from _common import block, git, project_dir, read_stdin_json, utf8_streams

BOOTSTRAP_MARKER = Path(".claude") / "BOOTSTRAP"
EVAL_ENV = "CTCV_ALLOW_EVAL_THRESHOLD"
ALWAYS_ALLOW = ("eval/redteam/**", "docs/security/**", ".claude/agent-memory/**")
ALWAYS_BLOCK: tuple[tuple[str, str], ...] = (
    ("docs/prompt-log/**", "docs/prompt-log/** chỉ do hook promptlog ghi (BTC cấm sửa prompt log)"),
    ("data/registry/*.lock", "data/registry/*.lock do pipeline dữ liệu sinh, không sửa tay"),
    (
        "docs/dossier/private/**",
        "docs/dossier/private/** chứa thông tin cá nhân đội (D25) — người dùng tự sửa",
    ),
)
MIGRATION_GLOB = "services/api/alembic/versions/*"
EVAL_FILE = "config/eval.yaml"
BOOTSTRAP_PROTECTED = (
    ".claude/**",
    "CLAUDE.md",
    ".github/workflows/**",
    ".pre-commit-config.yaml",
    "Makefile",
)


def _match(rel: str, pattern: str) -> bool:
    """Glob match with ``**`` semantics; case-insensitive on Windows file systems."""
    if os.name == "nt":
        rel, pattern = rel.lower(), pattern.lower()
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel == prefix or rel.startswith(prefix + "/")
    if "/" not in pattern:
        return fnmatch.fnmatchcase(rel, pattern) and "/" not in rel
    return fnmatch.fnmatchcase(rel, pattern)


def on_main(root: Path, rel: str) -> bool:
    """True when ``rel`` exists on branch ``main`` (fail-open: False without git/HEAD)."""
    code, _ = git(["cat-file", "-e", f"main:{rel}"], root)
    return code == 0


def relative_path(data: dict, root: Path) -> str | None:
    """Repo-relative POSIX path of the file being edited, or ``None`` when outside."""
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        block("protect-paths không đọc được tool_input — chặn để an toàn (fail-closed)")
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(raw, str) or not raw.strip():
        block("protect-paths không đọc được đường dẫn file — chặn để an toàn (fail-closed)")
    candidate = Path(raw.replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def decide(rel: str, root: Path, env: dict[str, str]) -> str | None:
    """Return a Vietnamese block reason for ``rel`` or ``None`` when the write is allowed."""
    if any(_match(rel, pattern) for pattern in ALWAYS_ALLOW):
        return None
    for pattern, reason in ALWAYS_BLOCK:
        if _match(rel, pattern):
            return reason
    if _match(rel, MIGRATION_GLOB) and on_main(root, rel):
        return f"{rel} là migration đã merge vào main — tạo migration mới thay vì sửa"
    if _match(rel, EVAL_FILE) and env.get(EVAL_ENV) != "1" and on_main(root, rel):
        return "config/eval.yaml chứa ngưỡng eval — chỉ sửa qua ADR với CTCV_ALLOW_EVAL_THRESHOLD=1"
    if any(_match(rel, pattern) for pattern in BOOTSTRAP_PROTECTED):
        if not (root / BOOTSTRAP_MARKER).exists():
            return (
                f"{rel} là cấu hình Claude Code/CI — chỉ sửa qua ADR được duyệt "
                "(marker .claude/BOOTSTRAP không còn)"
            )
    return None


def main() -> int:
    """Hook entry point: fail closed on parse errors, exit 2 to block."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        block(f"protect-paths không đọc được dữ liệu hook ({error}) — chặn để an toàn")
    root = project_dir(data)
    rel = relative_path(data, root)
    if rel is None:
        return 0
    reason = decide(rel, root, dict(os.environ))
    if reason:
        block(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
