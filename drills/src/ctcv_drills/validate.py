"""CLI: ``python -m ctcv_drills.validate [paths...]``.

Validates drill files (default: every ``drills/scenarios/*.json``). Directories are
expanded to their ``*.json`` files. Exit code 1 when any issue is found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ctcv_core.paths import DRILLS_DIR
from ctcv_drills.loader import drill_files
from ctcv_drills.rules import load_rules
from ctcv_drills.validator import Code, Issue, load_style, validate_file


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def expand_paths(args: list[str]) -> list[Path]:
    """Turn CLI arguments into files: directories → their ``*.json`` files."""
    paths: list[Path] = []
    for arg in args:
        path = Path(arg)
        paths.extend(drill_files(path) if path.is_dir() else [path])
    return paths


def _identity(path: Path) -> tuple[str, int] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "key" not in data:
        return None
    return str(data["key"]), int(data.get("variant", 1) or 1)


def _duplicate_issue(path: Path, seen: dict[tuple[str, int], Path]) -> list[Issue]:
    identity = _identity(path)
    if identity is None:
        return []
    first = seen.setdefault(identity, path)
    if first == path:
        return []
    return [
        Issue(
            code=Code.DUPLICATE_DRILL,
            message=f"key '{identity[0]}' biến thể {identity[1]} đã có trong {first.name}.",
            path="key",
        )
    ]


def _report(path: Path, issues: list[Issue], quiet: bool) -> None:
    if issues:
        print(f"LỖI  {path}")
        for issue in issues:
            print(f"  - {issue}")
    elif not quiet:
        print(f"OK   {path}")


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(prog="python -m ctcv_drills.validate", description=__doc__)
    parser.add_argument("paths", nargs="*", help="file .json hoặc thư mục (mặc định: scenarios/)")
    parser.add_argument("--quiet", action="store_true", help="chỉ in file lỗi")
    ns = parser.parse_args(argv)
    paths = expand_paths(ns.paths) or drill_files(DRILLS_DIR)
    rules, style = load_rules(), load_style()
    seen: dict[tuple[str, int], Path] = {}
    failed = 0
    for path in paths:
        issues = validate_file(path, rules, style) + _duplicate_issue(path, seen)
        _report(path, issues, ns.quiet)
        failed += bool(issues)
    print(f"Đã kiểm tra {len(paths)} kịch bản, {failed} file lỗi.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
