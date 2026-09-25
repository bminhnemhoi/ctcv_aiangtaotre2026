"""Stop hook (brief D4): non-blocking reminder + 'Phiên gần nhất' in DAILY.md.

If ``git status`` shows changes under ``services/ apps/ sandbox/ drills/ libs/`` and
``docs/status/last_check.json`` is older than the newest changed file (or missing),
a reminder to run ``make check QUICK=1`` is emitted as a ``systemMessage`` (visible,
never blocking). The ``## Phiên gần nhất`` section of ``docs/status/DAILY.md`` is
rewritten when it exists. Always exits 0 (``make daily`` pipes ``{}``).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from _common import (
    eprint,
    git,
    git_branch,
    git_head_short,
    now_iso,
    project_dir,
    read_stdin_json,
    replace_section,
    utf8_streams,
)

CODE_DIRS = ("services/", "apps/", "sandbox/", "drills/", "libs/")
DAILY = Path("docs") / "status" / "DAILY.md"
LAST_CHECK = Path("docs") / "status" / "last_check.json"
SECTION = "Phiên gần nhất"
REMINDER = (
    "Nhắc (không chặn): có {n} file mã thay đổi sau lần `make check` gần nhất ({when}) — "
    "chạy `make check QUICK=1` trước khi mở PR."
)


def changed_code_files(root: Path) -> list[str]:
    """Changed paths under the code directories according to ``git status``."""
    code, out = git(["status", "--porcelain"], root)
    if code != 0:
        return []
    files = []
    for line in out.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path.startswith(CODE_DIRS):
            files.append(path)
    return files


def newest_mtime(root: Path, files: list[str]) -> float | None:
    """Most recent modification time among ``files`` that still exist."""
    stamps = []
    for rel in files:
        try:
            stamps.append((root / rel).stat().st_mtime)
        except OSError:
            continue
    return max(stamps) if stamps else None


def last_check(root: Path) -> dict | None:
    """Parsed ``last_check.json`` or ``None``."""
    try:
        data = json.loads((root / LAST_CHECK).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def check_is_stale(root: Path, files: list[str]) -> tuple[bool, str]:
    """``(stale, description)`` — stale when code changed after the last green check."""
    info = last_check(root)
    if not files:
        return False, "không có thay đổi mã"
    if info is None or not info.get("ok"):
        return True, "chưa có/đỏ"
    try:
        checked = datetime.fromisoformat(str(info.get("ts"))).timestamp()
    except (TypeError, ValueError):
        return True, "thời điểm không đọc được"
    newest = newest_mtime(root, files)
    if newest is not None and newest > checked:
        return True, str(info.get("ts"))
    return False, str(info.get("ts"))


def update_daily(root: Path, lines: list[str]) -> bool:
    """Rewrite the 'Phiên gần nhất' section; False when DAILY.md/section is missing."""
    path = root / DAILY
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    updated = replace_section(text, SECTION, lines)
    if updated is None:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    """Hook entry point; always exits 0."""
    utf8_streams()
    data, _ = read_stdin_json()
    data = data or {}
    root = project_dir(data)
    files = changed_code_files(root)
    stale, when = check_is_stale(root, files)
    session_lines = [
        f"- Thời điểm (UTC): {now_iso()} · session_id: {data.get('session_id', '(không rõ)')}",
        f"- Nhánh: {git_branch(root)} · HEAD: {git_head_short(root)}",
        f"- Thay đổi mã chưa qua make check: {'CÓ' if stale else 'không'} "
        f"({len(files)} file; make check gần nhất: {when})",
    ]
    try:
        update_daily(root, session_lines)
    except OSError as exc:
        eprint(f"daily: không cập nhật được DAILY.md ({exc})")
    if stale:
        message = REMINDER.format(n=len(files), when=when)
        eprint(message)
        if data.get("hook_event_name"):
            print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        else:
            print(message)
    elif not data.get("hook_event_name"):
        print("daily: không có thay đổi mã ngoài lần make check gần nhất.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
