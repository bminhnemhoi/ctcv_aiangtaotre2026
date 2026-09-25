"""Suite results, threshold rows and the Markdown/JSON reports of the harness."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ctcv_eval.thresholds import BLOCK, PASS, SuiteThresholds, Verdict, format_value

Status = Literal["ran", "skipped"]
REPORTS_DIRNAME = "reports"
LATEST_JSON = "latest.json"
NO_THRESHOLD = "—"


@dataclass(slots=True)
class SuiteResult:
    """What one suite produced: ``ran`` with metrics, or ``skipped`` with a Vietnamese reason."""

    name: str
    metrics: dict[str, float] = field(default_factory=dict)
    status: Status = "ran"
    reason: str = ""
    samples: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def skipped(cls, name: str, reason: str, **details: Any) -> SuiteResult:
        """A suite that could not run yet (no eval set, no staging, later epic)."""
        return cls(name=name, status="skipped", reason=reason, details=dict(details))

    @property
    def ran(self) -> bool:
        """True when metrics are real numbers from an actual run."""
        return self.status == "ran"


@dataclass(frozen=True, slots=True)
class MetricRow:
    """One line of the ``metric | value | accept | block | verdict`` table."""

    suite: str
    metric: str
    value: float
    unit: str
    accept: float | None
    block: float | None
    verdict: str

    @property
    def blocked(self) -> bool:
        """True when the value breaches the block threshold."""
        return self.verdict == BLOCK


def evaluate_rows(
    results: Iterable[SuiteResult], thresholds: Mapping[str, SuiteThresholds]
) -> list[MetricRow]:
    """Turn ran suites into rows; metrics without a threshold get the ``—`` verdict."""
    rows: list[MetricRow] = []
    for result in results:
        if not result.ran:
            continue
        suite = thresholds.get(result.name)
        for name, value in result.metrics.items():
            metric = suite.metrics.get(name) if suite else None
            if metric is None:
                rows.append(MetricRow(result.name, name, value, "", None, None, NO_THRESHOLD))
                continue
            rows.append(
                MetricRow(
                    result.name,
                    name,
                    value,
                    metric.unit,
                    metric.accept,
                    metric.block,
                    metric.verdict(value),
                )
            )
    return rows


def has_block(rows: Iterable[MetricRow]) -> bool:
    """True when any row breaches its block threshold (the harness then exits 1)."""
    return any(row.blocked for row in rows)


def overall_verdict(rows: Iterable[MetricRow], results: Iterable[SuiteResult]) -> Verdict | str:
    """``CHẶN`` on any block, ``ĐẠT`` when every ran metric passes, else ``CẢNH BÁO``."""
    listed = list(rows)
    if any(r.blocked for r in listed):
        return BLOCK
    if not any(res.ran for res in results):
        return "CHƯA CHẠY"
    return PASS if all(r.verdict in (PASS, NO_THRESHOLD) for r in listed) else "CẢNH BÁO"


def _fmt(value: float | None, unit: str) -> str:
    return NO_THRESHOLD if value is None else format_value(value, unit)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_(không có dòng nào)_\n"
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(rows_) + " |" for rows_ in rows]
    return "\n".join(out) + "\n"


def render_report(
    results: list[SuiteResult],
    rows: list[MetricRow],
    thresholds: Mapping[str, SuiteThresholds],
    *,
    quick: bool,
    generated_at: dt.datetime | None = None,
) -> str:
    """Vietnamese Markdown report: summary per suite, metric table, verdict, unmet results."""
    stamp = (generated_at or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds")
    mode = "quick (CI, 100 mẫu)" if quick else "đầy đủ"
    summary_rows = [
        [
            thresholds[r.name].title if r.name in thresholds else r.name,
            "đã chạy" if r.ran else "bỏ qua",
            r.reason if not r.ran else f"{r.samples} mẫu",
        ]
        for r in results
    ]
    metric_rows = [
        [
            row.suite,
            row.metric,
            format_value(row.value, row.unit) if row.unit else f"{row.value:g}",
            _fmt(row.accept, row.unit),
            _fmt(row.block, row.unit),
            row.verdict,
        ]
        for row in rows
    ]
    unmet = [f"- Bộ **{r.name}** chưa chạy: {r.reason}" for r in results if not r.ran]
    unmet += [
        f"- **{row.suite}.{row.metric}** = {row.value:g} → {row.verdict}"
        for row in rows
        if row.verdict not in (PASS, NO_THRESHOLD)
    ]
    parts = [
        f"# Báo cáo đánh giá — {stamp[:10]} ({mode})\n",
        f"Sinh tự động bởi `python -m ctcv_eval.harness{' --quick' if quick else ''}` lúc {stamp}. "
        "Ngưỡng chấp nhận/chặn lấy từ `config/eval.yaml` (plan §7); không sửa tay.\n",
        "## Tóm tắt các bộ\n",
        _table(["Bộ", "Trạng thái", "Lý do / số mẫu"], summary_rows),
        "## Chỉ số so với ngưỡng\n",
        _table(["Bộ", "Chỉ số", "Giá trị", "Chấp nhận", "Chặn", "Kết luận"], metric_rows),
        "## Kết luận\n",
        f"**{overall_verdict(rows, results)}** — mã thoát 1 chỉ khi một bộ đã chạy "
        "vượt ngưỡng chặn.\n",
        "## Kết quả chưa đạt\n",
        "\n".join(unmet) if unmet else "- Không có.",
        "",
    ]
    return "\n".join(parts)


def reports_dir(root: Path) -> Path:
    """``<root>/eval/reports``."""
    return root / "eval" / REPORTS_DIRNAME


def write_report(directory: Path, text: str, date: dt.date) -> Path:
    """Write ``<directory>/<YYYY-MM-DD>.md`` and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{date.isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_latest_json(
    directory: Path, results: list[SuiteResult], rows: list[MetricRow], *, quick: bool
) -> Path:
    """Machine-readable twin of the report (``eval/reports/latest.json``, read by the dossier).

    Each suite carries ``status``, ``reason``, ``samples``, ``metrics`` and ``details``
    (ADR-007 C8: ``suites.qa.details.kb`` …); values JSON cannot encode become text.
    """
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "quick": quick,
        "ok": not has_block(rows),
        "suites": {
            r.name: {
                "status": r.status,
                "reason": r.reason,
                "samples": r.samples,
                "metrics": r.metrics,
                "details": r.details,
            }
            for r in results
        },
        "rows": [
            {
                "suite": row.suite,
                "metric": row.metric,
                "value": row.value,
                "accept": row.accept,
                "block": row.block,
                "verdict": row.verdict,
            }
            for row in rows
        ],
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LATEST_JSON
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    path.write_text(text + "\n", encoding="utf-8")
    return path
