"""Gate calibration on the **dev** split: ``uv run python -m ctcv_eval.calibrate_tthc``.

Routes every dev question once (``engine.route``: intent, first procedure, dense score and
title overlap), then replays the answer gate of :mod:`ctcv_agent.ask` offline over the grid
``min_dense_score ∈ {0.35 … 0.65}`` × ``title_overlap_min ∈ {0.2, 0.34, 0.5}``:

``passed = procedure found and dense ≥ min_dense and (overlap ≥ overlap_min or dense ≥ high)``

Questions stopped by the safety checks (OTP, real action, pasted content) are refused
whatever the thresholds. For each cell: ``refusal_accuracy`` (refuse items not passed or
stopped) and ``false_escalation_rate`` (answer items not passed). The proposal maximises
``refusal_accuracy`` under ``false_escalation_rate ≤ 15 %`` (ties: lower false
escalation, then the cell nearest the current config). The template fallback and the
embedder's degraded mode are not replayed. Writes ``eval/reports/calibration-tthc.md``;
**never edits** ``config/rag.yaml`` — a person decides. Questions are never written.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ctcv_agent.guardrails import (
    looks_like_pasted_content,
    refuses_real_action,
    refuses_sensitive_request,
)
from ctcv_agent.rag.settings import load_rag_settings
from ctcv_core.config import find_repo_root
from ctcv_eval.suites.qa import load_items
from ctcv_eval.tthc_metrics import pct

DENSE_GRID: tuple[float, ...] = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
OVERLAP_GRID: tuple[float, ...] = (0.2, 0.34, 0.5)
MAX_FALSE_ESCALATION = 15.0
CALIBRATION_SPLIT = "dev"
OUT_NAME = "calibration-tthc.md"


class Router(Protocol):
    """Anything with ``route(question) -> RouteDecision`` (``AnswerEngine``)."""

    def route(self, question: str) -> Any:
        """Route one question."""
        ...


@dataclass(frozen=True)
class RouteRecord:
    """Route facts of one dev item (no question text)."""

    item_id: str
    expect: str
    safety: bool
    found: bool
    dense: float
    match: float


@dataclass(frozen=True)
class GridRow:
    """Result of one threshold cell."""

    min_dense: float
    overlap: float
    refusal_accuracy: float | None
    false_escalation_rate: float | None
    n_refuse: int
    n_answer: int


def _stopped_by_safety(question: str) -> bool:
    return (
        refuses_sensitive_request(question)
        or refuses_real_action(question)
        or looks_like_pasted_content(question)
    )


def collect_routes(engine: Router, items: Sequence[dict[str, Any]]) -> list[RouteRecord]:
    """Route every dev item once, sorted by id."""
    dev = sorted((i for i in items if i["split"] == CALIBRATION_SPLIT), key=lambda i: i["id"])
    records = []
    for item in dev:
        question = item["question"]
        safety = _stopped_by_safety(question)
        decision = engine.route(question)
        records.append(
            RouteRecord(
                item_id=item["id"],
                expect=item["expect"],
                safety=safety,
                found=decision.procedure_id is not None,
                dense=float(decision.dense),
                match=float(decision.match),
            )
        )
    return records


def _passes(r: RouteRecord, min_dense: float, overlap: float, high: float) -> bool:
    if r.safety or not r.found or r.dense < min_dense:
        return False
    return r.match >= overlap or r.dense >= high


def evaluate(routes: Sequence[RouteRecord], *, min_dense: float, overlap: float, high: float):
    """One :class:`GridRow` for the thresholds."""
    refuse = [r for r in routes if r.expect == "refuse_or_escalate"]
    answer = [r for r in routes if r.expect == "answer"]
    refused_ok = sum(not _passes(r, min_dense, overlap, high) for r in refuse)
    false_esc = sum(not r.safety and not _passes(r, min_dense, overlap, high) for r in answer)
    return GridRow(
        min_dense,
        overlap,
        pct(refused_ok, len(refuse)),
        pct(false_esc, len(answer)),
        len(refuse),
        len(answer),
    )


def grid(routes: Sequence[RouteRecord], high: float) -> list[GridRow]:
    """Every cell of ``DENSE_GRID × OVERLAP_GRID``."""
    return [
        evaluate(routes, min_dense=d, overlap=o, high=high)
        for d in DENSE_GRID
        for o in OVERLAP_GRID
    ]


def recommend(
    rows: Sequence[GridRow],
    *,
    max_false_escalation: float = MAX_FALSE_ESCALATION,
    current: tuple[float, float] = (0.45, 0.34),
) -> GridRow | None:
    """Best cell under the false-escalation cap, or None when no cell satisfies it."""
    allowed = [
        r
        for r in rows
        if r.false_escalation_rate is not None and r.false_escalation_rate <= max_false_escalation
    ]
    if not allowed:
        return None

    def key(r: GridRow) -> tuple[float, float, float]:
        distance = abs(r.min_dense - current[0]) + abs(r.overlap - current[1])
        return (-(r.refusal_accuracy or 0.0), r.false_escalation_rate or 0.0, distance)

    return min(allowed, key=key)


def _cell(value: float | None) -> str:
    return "chưa đo" if value is None else f"{value:g}"


def render(rows: Sequence[GridRow], best: GridRow | None, current: tuple[float, float]) -> str:
    """Vietnamese Markdown report of the grid and the proposal."""
    n_refuse = rows[0].n_refuse if rows else 0
    n_answer = rows[0].n_answer if rows else 0
    lines = [
        f"# Hiệu chỉnh cổng trả lời TTHC — {dt.datetime.now(dt.UTC).date().isoformat()}\n",
        f"Tập `dev`: {n_answer} câu cần trả lời, {n_refuse} câu cần từ chối hoặc chuyển người. "
        "Sinh bởi `uv run python -m ctcv_eval.calibrate_tthc`; không tự sửa `config/rag.yaml`.\n",
        f"Cấu hình hiện tại: min_dense_score = {current[0]:g}, "
        f"title_overlap_min = {current[1]:g}.\n",
        "| min_dense_score | title_overlap_min | refusal_accuracy (%) "
        "| false_escalation_rate (%) |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r.min_dense:g} | {r.overlap:g} | {_cell(r.refusal_accuracy)} | "
            f"{_cell(r.false_escalation_rate)} |"
        )
    lines.append("\n## Đề xuất\n")
    if best is None:
        lines.append(f"Không ô nào có false_escalation_rate ≤ {MAX_FALSE_ESCALATION:g} %.")
    else:
        lines.append(
            f"min_dense_score = {best.min_dense:g}, title_overlap_min = {best.overlap:g} "
            f"(refusal_accuracy {_cell(best.refusal_accuracy)} %, false_escalation_rate "
            f"{_cell(best.false_escalation_rate)} %). Người phụ trách quyết định có đổi hay không."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, engine: Router | None = None) -> int:
    """CLI entry point (``engine`` is injectable for tests)."""
    parser = argparse.ArgumentParser(prog="python -m ctcv_eval.calibrate_tthc")
    parser.add_argument("--root", type=Path, default=None, help="gốc kho mã")
    parser.add_argument("--out", type=Path, default=None, help="tệp Markdown đầu ra")
    args = parser.parse_args(argv)
    root = (args.root or find_repo_root()).resolve()
    settings = load_rag_settings(root)
    if engine is None:
        from ctcv_agent.ask import build_engine

        engine = build_engine(settings, mode="template_only")
    gate = settings.gate
    current = (gate.min_dense_score, gate.title_overlap_min)
    rows = grid(collect_routes(engine, load_items(root)), gate.high_dense_score)
    best = recommend(rows, current=current)
    out = args.out or root / "eval" / "reports" / OUT_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows, best, current), encoding="utf-8")
    print(f"Đã ghi {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
