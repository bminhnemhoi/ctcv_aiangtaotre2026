"""CLI: ``python -m ctcv_eval.harness [--quick] [--suite name] [--report-dir PATH] [--root PATH]``.

``make eval`` (``QUICK=1`` → ``--quick``) calls this. Exit codes: 0 = no ran suite breaches a
block threshold (skipped suites never fail), 1 = a block threshold is breached, 2 = usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ctcv_eval.harness import SUITE_ALIASES, SUITE_ORDER, HarnessConfig, run_harness
from ctcv_eval.thresholds import format_value


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    """Argument parser (separate so tests can inspect it)."""
    parser = argparse.ArgumentParser(prog="python -m ctcv_eval.harness", description=__doc__)
    parser.add_argument(
        "--quick", action="store_true", help="bản 100 mẫu cho CI (make eval QUICK=1)"
    )
    parser.add_argument(
        "--suite",
        action="append",
        choices=(*SUITE_ORDER, *SUITE_ALIASES),
        help="chỉ chạy bộ này (lặp lại để chọn nhiều bộ)",
    )
    parser.add_argument("--root", type=Path, default=None, help="gốc kho mã (mặc định: tự tìm)")
    parser.add_argument("--report-dir", type=Path, default=None, help="thư mục báo cáo thay thế")
    parser.add_argument("--scenarios", type=Path, default=None, help="file red-team thay thế")
    parser.add_argument("--no-report", action="store_true", help="không ghi eval/reports")
    parser.add_argument("--list", action="store_true", help="liệt kê các bộ rồi thoát")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    args = build_parser().parse_args(argv)
    if args.list:
        for name in SUITE_ORDER:
            print(name)
        return 0
    cfg = HarnessConfig(
        quick=args.quick,
        report_dir=args.report_dir,
        scenarios_path=args.scenarios,
        write_reports=not args.no_report,
    )
    if args.root is not None:
        cfg.root = args.root.resolve()
    run = run_harness(cfg, args.suite)
    for result in run.results:
        if result.ran:
            shown = ", ".join(f"{k}={v:g}" for k, v in result.metrics.items())
            print(f"[ĐÃ CHẠY] {result.name}: {result.samples} mẫu — {shown}")
        else:
            print(f"[BỎ QUA] {result.name}: {result.reason}")
    for row in run.rows:
        value = format_value(row.value, row.unit) if row.unit else f"{row.value:g}"
        print(f"  {row.suite}.{row.metric} = {value} → {row.verdict}")
    if run.report_path:
        print(f"Báo cáo: {run.report_path}")
    if run.exit_code:
        print("CHẶN: có chỉ số vượt ngưỡng chặn (config/eval.yaml).")
    return run.exit_code


if __name__ == "__main__":
    sys.exit(main())
