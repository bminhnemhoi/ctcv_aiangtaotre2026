"""CLI: ``python -m ctcv_eval.redteam [--scenarios PATH] [--report-dir PATH] [--with-model]``.

``make redteam`` (inside ``make check``) runs this with no arguments: every scenario of
``eval/redteam/scenarios.jsonl`` goes through the guardrails with a model-free planner and
the report lands in ``eval/reports/redteam-<date>.md``. Exit 1 on any failing scenario.
``--with-model`` (``make redteam-model``, part of ``make gate``) is E11 work and exits 0
with a notice for now.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from ctcv_core.errors import ValidationFailed
from ctcv_core.paths import REPO_ROOT
from ctcv_eval.redteam import (
    default_scenarios_path,
    load_scenarios,
    render_report,
    run_scenarios,
    summarize,
    write_report,
)
from ctcv_eval.results import reports_dir

WITH_MODEL_NOTICE = "CHƯA HIỆN THỰC — E11 (red-team có model chạy trong make gate trên máy GPU)"


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    """Argument parser (separate so tests can inspect it)."""
    parser = argparse.ArgumentParser(prog="python -m ctcv_eval.redteam", description=__doc__)
    parser.add_argument("--scenarios", type=Path, default=None, help="file JSONL thay thế")
    parser.add_argument("--report-dir", type=Path, default=None, help="thư mục báo cáo thay thế")
    parser.add_argument("--root", type=Path, default=None, help="gốc kho mã (mặc định: tự tìm)")
    parser.add_argument("--no-report", action="store_true", help="không ghi eval/reports")
    parser.add_argument("--with-model", action="store_true", help="red-team có model (E11)")
    parser.add_argument("--verbose", "-v", action="store_true", help="in từng kịch bản")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    args = build_parser().parse_args(argv)
    if args.with_model:
        print(WITH_MODEL_NOTICE)
        return 0
    root = args.root.resolve() if args.root else None
    path = args.scenarios or default_scenarios_path(root)
    try:
        scenarios = load_scenarios(path)
    except ValidationFailed as exc:
        print(f"[LỖI] {exc.message_vi}")
        return 1
    outcomes = run_scenarios(scenarios, root=root)
    summary = summarize(outcomes)
    for outcome in outcomes:
        if args.verbose or not outcome.passed:
            tag = "ĐẠT" if outcome.passed else "LỖI"
            detail = "; ".join(outcome.failures) or outcome.scenario.expected
            print(f"[{tag}] {outcome.scenario.id} ({outcome.scenario.category}): {detail}")
    print(
        f"Red-team: {summary.passed}/{summary.total} đạt, {summary.failed} lỗi, "
        f"rò rỉ {summary.leaks}, hành động thay người dùng {summary.real_actions}."
    )
    if not args.no_report:
        directory = args.report_dir or reports_dir(root or REPO_ROOT)
        today = dt.datetime.now(dt.UTC).date()
        report = write_report(directory, render_report(outcomes, summary), today)
        print(f"Báo cáo: {report}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
