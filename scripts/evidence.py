"""Snapshot development evidence into ``docs/screens/YYYY-MM-DD/`` (``make evidence``, D20/D21).

Copies ``docs/status/DAILY.md`` and ``docs/status/last_check.json`` when present, writes a
``git-state.txt`` summary (branch, HEAD, short status, last commits) and lists the files.
UI screenshots are produced by the web e2e suite (``E2E=1 make e2e``) and land in the same
folder once apps/web exists; this script only reminds about them.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = (Path("docs") / "status" / "DAILY.md", Path("docs") / "status" / "last_check.json")
GIT_COMMANDS = (
    ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
    ("head", ["git", "rev-parse", "HEAD"]),
    ("status", ["git", "status", "--short"]),
    ("log", ["git", "log", "--oneline", "-10"]),
)


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def git_summary(root: Path) -> str:
    """Return a plain-text git summary; tolerant of missing git or an empty repo."""
    lines = [f"captured_at: {datetime.now(UTC).isoformat(timespec='seconds')}"]
    for label, cmd in GIT_COMMANDS:
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), *cmd[1:]],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            output = (
                proc.stdout.strip()
                if proc.returncode == 0
                else f"(không có: {proc.stderr.strip()[:80]})"
            )
        except (OSError, subprocess.TimeoutExpired):
            output = "(git không chạy được)"
        lines.append(f"## {label}\n{output}")
    return "\n".join(lines) + "\n"


def snapshot(root: Path, day: str | None = None) -> Path:
    """Create ``docs/screens/<day>/`` with copies of the status files and the git summary."""
    folder = root / "docs" / "screens" / (day or datetime.now(UTC).strftime("%Y-%m-%d"))
    folder.mkdir(parents=True, exist_ok=True)
    for rel in SOURCES:
        src = root / rel
        if src.is_file():
            shutil.copy2(src, folder / src.name)
    (folder / "git-state.txt").write_text(git_summary(root), encoding="utf-8")
    return folder


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--day", default=None, help="YYYY-MM-DD (mặc định: hôm nay, UTC)")
    args = parser.parse_args(argv)
    folder = snapshot(args.root, args.day)
    names = sorted(p.name for p in folder.iterdir())
    print(f"Đã lưu minh chứng vào {folder.relative_to(args.root)}: {', '.join(names)}")
    if not (args.root / "apps" / "web" / "package.json").is_file():
        print("Ảnh màn hình: chưa có apps/web — chạy `E2E=1 make e2e` sau khi web có (E02).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
