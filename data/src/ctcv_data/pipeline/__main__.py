"""CLI: ``python -m ctcv_data.pipeline [step] [--online] [--root PATH] [--update-hashes]``.

Directory overrides: ``--raw-dir``, ``--clean-dir``, ``--registry-dir``.

Without a step every step runs in plan §7 order (this is ``make data``). Exit codes:
0 = every step ok/skipped, 1 = a step failed, 2 = usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ctcv_data.pipeline import STEP_EPICS, STEP_ORDER, PipelineConfig, StepReport, run_steps


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    """Argument parser (kept separate so tests can inspect it)."""
    parser = argparse.ArgumentParser(prog="python -m ctcv_data.pipeline", description=__doc__)
    parser.add_argument("step", nargs="?", choices=(*STEP_ORDER, "all"), default="all")
    parser.add_argument("--online", action="store_true", help="cho phép truy cập mạng (robots.txt)")
    parser.add_argument("--root", type=Path, default=None, help="gốc kho mã (mặc định: tự tìm)")
    parser.add_argument("--raw-dir", type=Path, default=None, help="thư mục data/raw thay thế")
    parser.add_argument("--clean-dir", type=Path, default=None, help="thư mục data/clean thay thế")
    parser.add_argument("--registry-dir", type=Path, default=None, help="thư mục registry thay thế")
    parser.add_argument(
        "--update-hashes", action="store_true", help="ghi sha256 tính được vào mục đang 'pending'"
    )
    parser.add_argument("--list", action="store_true", help="liệt kê các bước rồi thoát")
    return parser


def format_report(report: StepReport) -> str:
    """One console line per step."""
    tag = {"ok": "OK", "skipped": "BỎ QUA", "failed": "LỖI"}[report.status]
    line = f"[{tag}] {report.step}: {report.message}"
    if report.outputs:
        line += " → " + ", ".join(report.outputs)
    return line


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    args = build_parser().parse_args(argv)
    if args.list:
        for name in STEP_ORDER:
            print(f"{name:18s} {STEP_EPICS[name]}")
        return 0
    cfg = PipelineConfig(
        online=args.online,
        raw_dir=args.raw_dir,
        registry_dir=args.registry_dir,
        clean_dir=args.clean_dir,
    )
    if args.root is not None:
        cfg.root = args.root.resolve()
    cfg.update_hashes = args.update_hashes
    names = list(STEP_ORDER) if args.step == "all" else [args.step]
    reports = run_steps(names, cfg)
    for report in reports:
        print(format_report(report))
    return max(r.exit_code for r in reports)


if __name__ == "__main__":
    sys.exit(main())
