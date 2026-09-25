"""CLI: ``python -m ctcv_sandbox.validate [paths...]``.

Validates scenario files (default: every ``sandbox/scenarios/*.json``). Directories
are expanded to their ``*.json`` files. Exit code 1 when any issue is found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ctcv_core.paths import SCENARIOS_DIR
from ctcv_sandbox.loader import scenario_files
from ctcv_sandbox.validator import Code, Issue, load_rules, validate_file


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def expand_paths(args: list[str]) -> list[Path]:
    """Turn CLI arguments into files: directories → their ``*.json`` files."""
    paths: list[Path] = []
    for arg in args:
        path = Path(arg)
        paths.extend(scenario_files(path) if path.is_dir() else [path])
    return paths


def _scenario_id(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data.get("id") if isinstance(data, dict) else None


def _duplicate_issue(path: Path, seen: dict[str, Path]) -> list[Issue]:
    scenario_id = _scenario_id(path)
    if not scenario_id:
        return []
    first = seen.setdefault(scenario_id, path)
    if first == path:
        return []
    return [
        Issue(
            code=Code.DUPLICATE_SCENARIO_ID,
            message=f"id '{scenario_id}' đã dùng trong {first.name}.",
            path="id",
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
    parser = argparse.ArgumentParser(prog="python -m ctcv_sandbox.validate", description=__doc__)
    parser.add_argument("paths", nargs="*", help="file .json hoặc thư mục (mặc định: scenarios/)")
    parser.add_argument("--quiet", action="store_true", help="chỉ in file lỗi")
    ns = parser.parse_args(argv)
    paths = expand_paths(ns.paths) or scenario_files(SCENARIOS_DIR)
    rules = load_rules()
    seen: dict[str, Path] = {}
    failed = 0
    for path in paths:
        issues = validate_file(path, rules) + _duplicate_issue(path, seen)
        _report(path, issues, ns.quiet)
        failed += bool(issues)
    print(f"Đã kiểm tra {len(paths)} kịch bản, {failed} file lỗi.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
