"""Documentation gate for ``make docs-check``.

Fails (exit 1) when README.md lacks a required section, CHANGELOG.md has no
``[Unreleased]`` entry, or ``docs/prompt-log/INDEX.md`` is missing. Messages are
Vietnamese so the team sees exactly what to fix.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Section name → keywords, any of which may appear in a level-2 heading (case-insensitive).
REQUIRED_README_SECTIONS: dict[str, tuple[str, ...]] = {
    "Chạy nhanh": ("chạy nhanh", "bắt đầu nhanh", "quick start"),
    "Yêu cầu": ("yêu cầu", "chuẩn bị", "prerequisites"),
    "Cấu trúc kho mã": ("cấu trúc", "thư mục", "repo map"),
    "Lệnh chuẩn": ("lệnh chuẩn", "lệnh thường dùng", "commands"),
    "Tài liệu": ("tài liệu", "docs"),
    "Giấy phép": ("giấy phép", "license"),
}
UNRELEASED_RE = re.compile(r"^## \[Unreleased\]", re.MULTILINE)
RELEASE_HEADING_RE = re.compile(r"^## \[", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*[-*] \S", re.MULTILINE)


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _headings(markdown: str) -> list[str]:
    return [line[3:].strip().lower() for line in markdown.splitlines() if line.startswith("## ")]


def check_readme(root: Path) -> list[str]:
    """Return problems with README.md (missing file or missing sections)."""
    path = root / "README.md"
    if not path.is_file():
        return ["Thiếu README.md ở gốc kho mã."]
    headings = _headings(path.read_text(encoding="utf-8"))
    problems = []
    for section, keywords in REQUIRED_README_SECTIONS.items():
        if not any(any(word in heading for word in keywords) for heading in headings):
            problems.append(
                f"README.md thiếu mục cấp 2 '{section}' (từ khóa: {', '.join(keywords)})."
            )
    return problems


def check_changelog(root: Path) -> list[str]:
    """Return problems with CHANGELOG.md (needs an [Unreleased] block with ≥ 1 bullet)."""
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return ["Thiếu CHANGELOG.md ở gốc kho mã."]
    text = path.read_text(encoding="utf-8")
    match = UNRELEASED_RE.search(text)
    if not match:
        return ["CHANGELOG.md không có mục '## [Unreleased]'."]
    rest = text[match.end() :]
    next_heading = RELEASE_HEADING_RE.search(rest)
    block = rest[: next_heading.start()] if next_heading else rest
    if not BULLET_RE.search(block):
        return ["Mục [Unreleased] trong CHANGELOG.md chưa có dòng thay đổi nào (gạch đầu dòng)."]
    return []


def check_prompt_log_index(root: Path) -> list[str]:
    """Return problems with docs/prompt-log/INDEX.md (must exist and be non-empty)."""
    path = root / "docs" / "prompt-log" / "INDEX.md"
    if not path.is_file():
        return ["Thiếu docs/prompt-log/INDEX.md — prompt log là minh chứng bắt buộc của BTC."]
    if not path.read_text(encoding="utf-8").strip():
        return ["docs/prompt-log/INDEX.md đang rỗng (cần ít nhất header bảng)."]
    return []


def run_checks(root: Path) -> list[str]:
    """Run every documentation check and return the list of problems."""
    return [*check_readme(root), *check_changelog(root), *check_prompt_log_index(root)]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    problems = run_checks(args.root)
    for problem in problems:
        print(f"LỖI: {problem}")
    if problems:
        print(f"docs-check: {len(problems)} vấn đề cần sửa.")
        return 1
    print("docs-check OK: README đủ mục, CHANGELOG có [Unreleased], prompt-log INDEX có mặt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
