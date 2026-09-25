"""Write ``docs/status/last_check.json`` at the end of a green ``make check``.

The Claude Code hooks (session-start, daily) read this file to remind the team when
code changed after the last successful check. Payload: ``{ts, git_head, ok, quick}``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = Path("docs") / "status" / "last_check.json"
NO_GIT = "nogit"


def git_head(root: Path) -> str:
    """Return the current commit hash, or ``"nogit"`` outside a repo / before the first commit."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return NO_GIT
    head = result.stdout.strip()
    return head if result.returncode == 0 and head else NO_GIT


def write_last_check(root: Path, ok: bool = True, quick: bool = False) -> Path:
    """Write the status file under ``root`` and return its path."""
    payload = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_head": git_head(root),
        "ok": ok,
        "quick": quick,
    }
    path = root / STATUS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--fail", action="store_true", help="record ok=false")
    parser.add_argument("--quick", action="store_true", help="record that QUICK=1 was used")
    args = parser.parse_args(argv)
    quick = args.quick or os.environ.get("QUICK") == "1"
    path = write_last_check(args.root, ok=not args.fail, quick=quick)
    label = "đỏ" if args.fail else "xanh"
    print(f"Đã ghi kết quả make check ({label}) vào {path.relative_to(args.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
