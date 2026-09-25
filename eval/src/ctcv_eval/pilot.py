"""``python -m ctcv_eval.pilot kit|report`` — entry point of the two pilot Makefile targets.

Targets: ``make pilot-kit`` and ``make pilot-report``.

E01 only validates the pilot log CSV against the schema documented in ``eval/pilot/README.md``
(``make pilot-report``); the kit generator and the before/after report with bootstrap
confidence intervals land in the PILOT epic. Rows are aggregate, anonymous measurements:
any column that looks like PII is rejected outright (docs/pilot/README.md §3).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ctcv_core.paths import REPO_ROOT

DEFAULT_CSV = ("eval", "pilot", "log.csv")
MIN_FORMAL_N = 30
KIT_NOTICE = "CHƯA HIỆN THỰC — PILOT (make pilot-kit sinh tài liệu buổi học ở epic PILOT)"

# column → (required, validator regex); blank is allowed for optional columns.
COLUMNS: dict[str, tuple[bool, str]] = {
    "participant_code": (True, r"^[A-Za-z0-9_-]{2,16}$"),
    "group": (True, r"^[AB]$"),
    "session": (True, r"^[12]$"),
    "skill": (True, r"^[a-z0-9-]+$"),
    "completed_unaided": (True, r"^[01]$"),
    "duration_s": (True, r"^\d+$"),
    "mistakes": (True, r"^\d+$"),
    "hints": (True, r"^\d+$"),
    "drill_score_before": (False, r"^(100|[1-9]?\d)$"),
    "drill_score_after": (False, r"^(100|[1-9]?\d)$"),
    "sus": (False, r"^(100|[1-9]?\d)$"),
    "returned_day5": (False, r"^[01]$"),
}
PII_COLUMN_RE = re.compile(
    r"(?i)(name|ho[_ ]?ten|ten|phone|sdt|dien[_ ]?thoai|email|cccd|can[_ ]?cuoc"
    r"|dia[_ ]?chi|address|birth|ngay[_ ]?sinh)"
)


@dataclass(slots=True)
class PilotCsvReport:
    """Validation outcome of a pilot log CSV."""

    path: Path
    rows: int = 0
    participants: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no problem was found."""
        return not self.problems

    @property
    def preliminary(self) -> bool:
        """True when fewer than 30 participants (tier 1 — no statistical inference)."""
        return self.participants < MIN_FORMAL_N


def _check_header(header: list[str], report: PilotCsvReport) -> None:
    for column in header:
        if PII_COLUMN_RE.search(column) and column not in COLUMNS:
            report.problems.append(f"cột '{column}' trông như PII — không được có trong log pilot")
    missing = [c for c, (required, _) in COLUMNS.items() if required and c not in header]
    if missing:
        report.problems.append("thiếu cột bắt buộc: " + ", ".join(missing))
    unknown = [c for c in header if c not in COLUMNS and not PII_COLUMN_RE.search(c)]
    if unknown:
        report.problems.append("cột lạ: " + ", ".join(unknown))


def _check_row(number: int, row: dict[str, str], report: PilotCsvReport) -> None:
    for column, (required, pattern) in COLUMNS.items():
        value = (row.get(column) or "").strip()
        if not value:
            if required:
                report.problems.append(f"dòng {number}: thiếu '{column}'")
            continue
        if not re.match(pattern, value):
            report.problems.append(f"dòng {number}: '{column}' = {value!r} không hợp lệ")


def validate_csv(path: Path, *, max_problems: int = 50) -> PilotCsvReport:
    """Validate header and rows of the pilot log CSV (schema in ``eval/pilot/README.md``)."""
    report = PilotCsvReport(path=path)
    if not path.is_file():
        report.problems.append(f"thiếu file {path}")
        return report
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = [h.strip() for h in (reader.fieldnames or [])]
        if not header:
            report.problems.append("file CSV rỗng (không có dòng tiêu đề)")
            return report
        _check_header(header, report)
        codes: set[str] = set()
        for number, row in enumerate(reader, start=2):
            report.rows += 1
            _check_row(number, row, report)
            codes.add((row.get("participant_code") or "").strip())
            if len(report.problems) >= max_problems:
                report.problems.append("… (dừng sau 50 lỗi)")
                break
        report.participants = len(codes - {""})
    return report


def build_parser() -> argparse.ArgumentParser:
    """``kit`` or ``report [--csv PATH]``."""
    parser = argparse.ArgumentParser(prog="python -m ctcv_eval.pilot", description=__doc__)
    parser.add_argument("command", choices=("kit", "report"))
    parser.add_argument(
        "--csv", type=Path, default=None, help="log pilot (mặc định eval/pilot/log.csv)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: 0 = ok/notice, 1 = CSV invalid, 2 = usage."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.command == "kit":
        print(KIT_NOTICE)
        return 0
    path = args.csv or REPO_ROOT.joinpath(*DEFAULT_CSV)
    if args.csv is None and not path.is_file():
        print(f"Chưa có log pilot ({path}); báo cáo pilot sinh ở epic PILOT sau buổi học đầu.")
        return 0
    report = validate_csv(path)
    if not report.ok:
        print(f"[LỖI] log pilot không hợp lệ ({len(report.problems)} vấn đề):")
        for problem in report.problems:
            print(f"  - {problem}")
        return 1
    tier = "quy mô sơ bộ, không suy diễn thống kê" if report.preliminary else "tầng chính thức"
    print(
        f"[OK] {report.rows} dòng, {report.participants} người tham gia ({tier}). "
        "Bảng trước/sau và khoảng tin cậy bootstrap: epic PILOT."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
