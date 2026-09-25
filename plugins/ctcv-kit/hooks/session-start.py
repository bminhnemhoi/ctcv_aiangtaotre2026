"""SessionStart hook (brief §11): print the team's working memory into the context.

Shows the head of ``docs/status/DAILY.md``, the latest ``CHECKPOINT.md`` entry, the
``last_check.json`` summary, warns when ``.claude/BOOTSTRAP`` is present, self-tests
that Python and ``docs/prompt-log/`` are writable (loud warning otherwise) and imports
transcripts newer than two days from ``~/.claude/projects/<slug>/`` that are not in
INDEX yet (``promptlog.sync_transcripts``). Always exits 0 — exit 2 would block the
session.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import promptlog
from _common import (
    eprint,
    git_branch,
    git_head_short,
    project_dir,
    read_stdin_json,
    read_text,
    safe_id,
    utf8_streams,
)

DAILY_HEAD_LINES = 40
CHECKPOINT_LINES = 25
IMPORT_MAX_AGE_DAYS = 2
BOOTSTRAP = Path(".claude") / "BOOTSTRAP"
LOUD = "!!! CẢNH BÁO LỚN !!!"


def bootstrap_warning(root: Path) -> list[str]:
    """Warn while the E01 bootstrap marker disables protection of the Claude config."""
    if not (root / BOOTSTRAP).exists():
        return []
    return [
        f"{LOUD} .claude/BOOTSTRAP đang tồn tại: protect-paths KHÔNG bảo vệ .claude/**, CLAUDE.md, "
        ".github/workflows/**, .pre-commit-config.yaml, Makefile. Xóa marker khi merge E01.",
    ]


def self_test(root: Path) -> list[str]:
    """Check that Python works and ``docs/prompt-log/`` accepts writes."""
    target = root / promptlog.PROMPT_LOG / promptlog.SESSIONS
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return [
            f"{LOUD} Không ghi được vào {target.as_posix()} ({exc}). Prompt log của phiên này "
            "SẼ KHÔNG được lưu — sửa quyền thư mục trước khi làm việc.",
        ]
    return [f"Hook OK: Python {sys.version.split()[0]}, docs/prompt-log/ ghi được."]


def last_check_summary(root: Path) -> str:
    """One line describing ``docs/status/last_check.json``."""
    path = root / "docs" / "status" / "last_check.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "make check: chưa có docs/status/last_check.json — chạy `make check QUICK=1`."
    ts = str(data.get("ts", "?"))
    age = ""
    try:
        delta = datetime.now(UTC) - datetime.fromisoformat(ts)
        age = f", cách đây {delta.total_seconds() / 3600:.1f} giờ"
    except ValueError:
        pass
    state = "XANH" if data.get("ok") else "ĐỎ"
    quick = " (QUICK=1)" if data.get("quick") else ""
    return f"make check gần nhất: {state}{quick} lúc {ts}{age}, HEAD {data.get('git_head', '?')}."


def checkpoint_excerpt(root: Path) -> list[str]:
    """The ``## Checkpoint gần nhất`` section of CHECKPOINT.md (truncated)."""
    text = read_text(root / "docs" / "status" / "CHECKPOINT.md")
    if not text:
        return []
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## Checkpoint")), None)
    if start is None:
        return lines[:CHECKPOINT_LINES]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end][:CHECKPOINT_LINES]


def import_transcripts(root: Path, data: dict) -> list[str]:
    """Import recent transcripts that never made it into INDEX (missing-hook sessions)."""
    cwd = str(data.get("cwd") or root)
    skip = {safe_id(data["session_id"])} if data.get("session_id") else set()
    try:
        imported = promptlog.sync_transcripts(root, cwd, IMPORT_MAX_AGE_DAYS, skip)
    except OSError as exc:
        return [f"Nhập transcript cũ thất bại: {exc}"]
    if not imported:
        return []
    return [
        f"Đã nhập {len(imported)} transcript phiên trước vào docs/prompt-log/sessions/: "
        + ", ".join(imported)
    ]


def build_context(root: Path, data: dict) -> list[str]:
    """Assemble the lines printed to stdout (added to Claude's context)."""
    lines = [
        "# CTCV — ngữ cảnh đầu phiên (hook session-start)",
        f"Lý do: {data.get('session_start_reason', data.get('source', 'startup'))} · "
        f"nhánh {git_branch(root)} · HEAD {git_head_short(root)} · "
        f"session {data.get('session_id', '?')}",
    ]
    lines += bootstrap_warning(root)
    lines += self_test(root)
    lines.append(last_check_summary(root))
    lines += import_transcripts(root, data)
    daily = read_text(root / "docs" / "status" / "DAILY.md")
    if daily:
        lines += ["", "## docs/status/DAILY.md (đầu file)"]
        lines += daily.splitlines()[:DAILY_HEAD_LINES]
    checkpoint = checkpoint_excerpt(root)
    if checkpoint:
        lines += ["", "## docs/status/CHECKPOINT.md"] + checkpoint
    lines += [
        "",
        "Nguồn sự thật: docs/idea.md > docs/plan.md > docs/prompt.md; quyết định E01: "
        "docs/decisions/E01-brief.md; yêu cầu BTC: docs/competition/BTC-2026-yeu-cau.md.",
    ]
    return lines


def main() -> int:
    """Hook entry point; never blocks."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        eprint(f"session-start: dữ liệu hook không đọc được ({error}) — tiếp tục với mặc định")
        data = {}
    try:
        print("\n".join(build_context(project_dir(data), data)))
    except Exception as exc:  # noqa: BLE001 — a SessionStart hook must never fail the session
        eprint(f"session-start: lỗi không mong đợi ({exc}) — bỏ qua")
    return 0


if __name__ == "__main__":
    sys.exit(main())
