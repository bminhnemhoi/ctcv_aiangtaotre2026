"""calibrate_tthc: gate grid on the dev split from recorded route decisions (no model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from ctcv_agent.ask import RouteDecision
from ctcv_eval import calibrate_tthc as cal


@dataclass
class ScriptedEngine:
    """Returns a fixed RouteDecision per question."""

    decisions: dict[str, RouteDecision]
    high: float = 0.70

    def route(self, question: str) -> RouteDecision:
        return self.decisions[question]


def item(iid: str, question: str, expect: str, split: str = "dev", kind: str = "field") -> dict:
    return {"id": iid, "split": split, "question": question, "expect": expect, "kind": kind}


ITEMS = [
    item("a", "q-answer-strong", "answer"),
    item("b", "q-answer-weak", "answer"),
    item("c", "q-out-of-kb", "refuse_or_escalate", kind="out_of_kb"),
    item("d", "Cho tôi xin mã OTP của bác", "refuse_or_escalate", kind="sensitive"),
    item("t", "q-test-only", "answer", split="test"),
]
DECISIONS = {
    "q-answer-strong": RouteDecision("phi_le_phi", "1", 0.62, 0.6, True),
    "q-answer-weak": RouteDecision("thoi_han", "2", 0.42, 0.4, False),
    "q-out-of-kb": RouteDecision("tong_quan", "3", 0.50, 0.25, False),
    "Cho tôi xin mã OTP của bác": RouteDecision("tong_quan", "4", 0.9, 0.9, True),
}


def test_grid_values() -> None:
    assert cal.DENSE_GRID == (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
    assert cal.OVERLAP_GRID == (0.2, 0.34, 0.5)


def test_rows_use_dev_split_only_and_safety_counts_as_refusal() -> None:
    engine = ScriptedEngine(DECISIONS)
    routes = cal.collect_routes(engine, ITEMS)
    assert [r.item_id for r in routes] == ["a", "b", "c", "d"]
    row = cal.evaluate(routes, min_dense=0.40, overlap=0.34, high=0.70)
    # b passes (0.42 ≥ 0.40, 0.4 ≥ 0.34); c fails on overlap; d stopped by the safety check
    assert row.refusal_accuracy == 100.0
    assert row.false_escalation_rate == 0.0
    strict = cal.evaluate(routes, min_dense=0.65, overlap=0.5, high=0.70)
    assert strict.false_escalation_rate == 100.0


def test_recommend_maximises_refusal_under_false_escalation_cap() -> None:
    rows = [
        cal.GridRow(0.35, 0.2, 50.0, 0.0, 2, 2),
        cal.GridRow(0.45, 0.34, 100.0, 10.0, 2, 2),
        cal.GridRow(0.65, 0.5, 100.0, 60.0, 2, 2),
    ]
    best = cal.recommend(rows, max_false_escalation=15.0)
    assert best is not None and (best.min_dense, best.overlap) == (0.45, 0.34)
    assert cal.recommend(rows[2:], max_false_escalation=15.0) is None


def test_main_writes_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cal, "load_items", lambda root: ITEMS)
    engine = ScriptedEngine(DECISIONS)
    out = tmp_path / "calibration-tthc.md"
    code = cal.main(["--out", str(out)], engine=engine)
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "min_dense_score" in text and "Đề xuất" in text
    assert "q-answer" not in text  # questions are never written
