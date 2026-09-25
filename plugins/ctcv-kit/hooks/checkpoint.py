"""PreCompact hook (brief §11): save the working state to ``docs/status/CHECKPOINT.md``.

Rewrites the ``## Checkpoint gần nhất`` section with what the hook can observe
(time, session, trigger, branch/HEAD, changed files, last ``make check``, current
epic from DAILY.md) and pushes the previous entry into ``## Lịch sử`` (kept ≤ 10).
``## Ghi chú tay`` is preserved. Never blocks.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _common import (
    eprint,
    git,
    git_branch,
    git_head_short,
    now_iso,
    project_dir,
    read_stdin_json,
    read_text,
    utf8_streams,
)

CHECKPOINT = Path("docs") / "status" / "CHECKPOINT.md"
LATEST = "Checkpoint gần nhất"
HISTORY = "Lịch sử"
NOTES = "Ghi chú tay"
MAX_HISTORY = 10
MAX_FILES = 12
EPIC_RE = re.compile(r"\bE(?:0[1-9]|1[0-2])\b")
TEMPLATE = (
    "# CHECKPOINT — Điểm lưu ngữ cảnh trước khi nén (hook `checkpoint.py` ở PreCompact ghi)\n\n"
    f"## {LATEST}\n- (chưa có)\n\n## {NOTES}\n- (trống)\n\n## {HISTORY}\n- (trống)\n"
)


def changed_files(root: Path) -> list[str]:
    """Paths reported by ``git status --porcelain`` (renames keep the new name)."""
    code, out = git(["status", "--porcelain"], root)
    if code != 0:
        return []
    files = []
    for line in out.splitlines():
        path = line[3:].split(" -> ")[-1].strip()
        if path:
            files.append(path)
    return files


def current_epic(root: Path) -> str:
    """Epic id mentioned first in the KPI row 'Epic đang làm' of DAILY.md."""
    for line in read_text(root / "docs" / "status" / "DAILY.md").splitlines():
        if "Epic đang làm" in line and "|" in line and "KPI" not in line:
            match = EPIC_RE.search(line)
            if match:
                return match.group(0)
    return "?"


def last_check_line(root: Path) -> str:
    """Compact description of docs/status/last_check.json."""
    try:
        data = json.loads((root / "docs" / "status" / "last_check.json").read_text("utf-8"))
    except (OSError, ValueError):
        return "chưa có last_check.json"
    state = "xanh" if data.get("ok") else "đỏ"
    return f"{state} lúc {data.get('ts', '?')} (HEAD {data.get('git_head', '?')})"


def build_entry(root: Path, data: dict) -> list[str]:
    """Bullet lines for the new checkpoint."""
    files = changed_files(root)
    shown = ", ".join(files[:MAX_FILES]) + (" …" if len(files) > MAX_FILES else "")
    return [
        f"- Thời điểm (UTC): {now_iso()}",
        f"- session_id: {data.get('session_id', '?')} (trigger: {data.get('trigger', '?')})",
        f"- Nhánh git / HEAD: {git_branch(root)} / {git_head_short(root)}",
        f"- Epic đang làm: {current_epic(root)}",
        f"- File đang thay đổi ({len(files)}): {shown or 'không có'}",
        f"- make check gần nhất: {last_check_line(root)}",
        "- Việc đã xong / đang dở / câu hỏi chờ: xem transcript phiên này "
        "(docs/prompt-log/sessions/) và DAILY.md — hook không đọc được nội dung hội thoại.",
    ]


def split_sections(text: str) -> tuple[str, dict[str, list[str]], list[str]]:
    """Split markdown into ``(preamble, {title: body_lines}, order)``."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            order.append(current)
        elif current is None:
            preamble.append(line)
        else:
            sections[current].append(line)
    return "\n".join(preamble).rstrip("\n"), sections, order


def rotate(sections: dict[str, list[str]], entry: list[str]) -> None:
    """Move the old latest entry into history (≤ MAX_HISTORY) and install ``entry``."""
    old = [line for line in sections.get(LATEST, []) if line.strip()]
    history = [line for line in sections.get(HISTORY, []) if line.strip() != "- (trống)"]
    if old and old != ["- (chưa có)"]:
        stamp = next((line for line in old if "Thời điểm" in line), old[0])
        history = [f"### {stamp.lstrip('- ')}", *old, ""] + history
    entries = "\n".join(history).split("### ")
    kept = "### ".join(entries[: MAX_HISTORY + 1]).rstrip("\n").splitlines()
    sections[LATEST] = entry + [""]
    sections[HISTORY] = (kept or ["- (trống)"]) + [""]
    sections.setdefault(NOTES, ["- (trống)", ""])


def render(preamble: str, sections: dict[str, list[str]], order: list[str]) -> str:
    """Serialise sections back to markdown, keeping the original order."""
    titles = [t for t in order if t in sections] + [t for t in sections if t not in order]
    parts = [preamble.rstrip("\n"), ""] if preamble else []
    for title in titles:
        body = "\n".join(sections[title]).rstrip("\n")
        parts += [f"## {title}", body, ""]
    return "\n".join(parts).rstrip("\n") + "\n"


def main() -> int:
    """Hook entry point; fails open."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        eprint(f"checkpoint: dữ liệu hook không đọc được ({error}) — ghi với thông tin tối thiểu")
        data = {}
    root = project_dir(data)
    path = root / CHECKPOINT
    try:
        text = read_text(path) or TEMPLATE
        preamble, sections, order = split_sections(text)
        rotate(sections, build_entry(root, data))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(preamble, sections, order), encoding="utf-8")
        eprint(f"checkpoint: đã ghi {CHECKPOINT.as_posix()}")
    except OSError as exc:
        eprint(f"checkpoint: không ghi được ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
