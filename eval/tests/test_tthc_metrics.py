"""tthc_metrics: C8 metric definitions on hand-built outcomes (no engine, no model)."""

from __future__ import annotations

import pytest

from ctcv_eval import tthc_metrics as m

SOURCE_FEE = (
    "Thủ tục Đăng ký thường trú (mã 1.004222) — Phí, lệ phí: Trực tiếp: thu 20.000 đồng/lần "
    "đăng ký. Trực tuyến: thu 10.000 đồng/lần đăng ký."
)
GOOD_CORE = (
    "Theo Cổng, phí đăng ký thường trú là nộp trực tiếp 20.000 đồng, trực tuyến 10.000 đồng."
)
BAD_CORE = "Phí đăng ký thường trú là 50.000 đồng."


def item(
    iid: str = "g-1",
    *,
    expect: str = "answer",
    gold: str | None = "1.004222",
    values: tuple[str, ...] = ("20.000", "10.000"),
    kind: str = "field",
) -> dict:
    return {
        "id": iid,
        "split": "test",
        "kind": kind,
        "question": "Đăng ký thường trú mất bao nhiêu tiền?",
        "expect": expect,
        "gold_procedure_id": gold,
        "gold_intent": "phi_le_phi" if gold else None,
        "expected_values": list(values),
        "source": "generated:tthc-template/1",
        "notes": "",
    }


def outcome(
    mode: str = "template",
    core: str | None = GOOD_CORE,
    *,
    pid: str | None = "1.004222",
    cited: tuple[str, ...] = (SOURCE_FEE,),
    card: str = "",
    escalate: bool = False,
    refused: bool = False,
    retrieved: tuple[str, ...] = ("1.004222",),
    latency: float = 1.0,
) -> m.Outcome:
    answer = f"{core} Bác bấm nút xanh có chữ Nguồn." if core else "Cháu chưa chắc."
    return m.Outcome(
        answer_mode=mode,
        answer=answer,
        core=core,
        procedure_id=pid,
        card_text=card,
        cited_texts=cited,
        has_citations=bool(cited),
        escalate=escalate,
        refused=refused,
        retrieved=retrieved,
        latency_s=latency,
    )


NO_SOURCE = outcome("no_source", None, pid=None, cited=(), escalate=True, retrieved=())


def test_metric_names_are_the_nine_c8_names() -> None:
    assert m.METRIC_NAMES == (
        "recall_at_5",
        "answer_accuracy",
        "citation_support",
        "hallucination",
        "numeric_fidelity",
        "refusal_accuracy",
        "false_escalation_rate",
        "latency_p50_s",
        "latency_p95_s",
    )


def test_value_present_numbers_and_words() -> None:
    assert m.value_present("20.000", "mất 20 nghìn đồng")
    assert m.value_present("07 Ngày làm việc", "thời hạn là 7 ngày làm việc")
    assert not m.value_present("07 Ngày làm việc", "thời hạn là 7 ngày")
    assert m.value_present("Chưa quy định", "phí ghi chua quy dinh")
    assert m.value_present("CT01", "tờ khai mẫu CT01")
    assert not m.value_present("20.000", "mất 10.000 đồng")


def test_answer_accuracy_uses_card_unless_text_only() -> None:
    card_only = outcome(core="Theo Cổng, xem thẻ bên dưới.", card="Trực tiếp 20000 ; 10000")
    pairs = [(item(), card_only)]
    assert m.compute_metrics(pairs, 0.5)["answer_accuracy"] == 100.0
    assert m.answer_accuracy(pairs, text_only=True) == 0.0


def test_answer_accuracy_needs_the_gold_procedure() -> None:
    wrong = outcome(pid="1.004194")
    assert m.compute_metrics([(item(), wrong)], 0.5)["answer_accuracy"] == 0.0


def test_citation_support_and_hallucination() -> None:
    pairs = [
        (item("a"), outcome()),
        (item("b"), outcome(core=BAD_CORE)),
        (item("c"), outcome(cited=())),
        (item("d"), NO_SOURCE),
    ]
    got = m.compute_metrics(pairs, 0.5)
    assert got["citation_support"] == pytest.approx(100 / 3, abs=0.01)
    assert got["hallucination"] == pytest.approx(200 / 3, abs=0.01)
    # b has an unsupported number, c has no source at all
    assert got["numeric_fidelity"] == pytest.approx(100 / 3, abs=0.01)
    assert got["false_escalation_rate"] == 25.0


def test_refusal_and_recall() -> None:
    refuse = item("r", expect="refuse_or_escalate", gold=None, values=(), kind="out_of_kb")
    safety = outcome("safety", None, pid=None, cited=(), refused=True, retrieved=())
    wrong_answer = outcome(pid="1.004222")
    pairs = [
        (refuse, safety),
        (refuse, NO_SOURCE),
        (refuse, wrong_answer),
        (item("x"), outcome(retrieved=("9", "8", "7", "6", "1.004222"))),
        (item("y"), outcome(retrieved=("9", "8", "7", "6", "5", "1.004222"))),
    ]
    got = m.compute_metrics(pairs, 0.5)
    assert got["refusal_accuracy"] == pytest.approx(200 / 3, abs=0.01)
    assert got["recall_at_5"] == 50.0


def test_undefined_metrics_are_omitted_not_invented() -> None:
    got = m.compute_metrics([(item(), outcome())], 0.5)
    assert "refusal_accuracy" not in got
    assert m.undefined_metrics(got) == ["refusal_accuracy"]


def test_latency_percentiles() -> None:
    pairs = [(item(str(i)), outcome(latency=float(i))) for i in range(1, 11)]
    got = m.compute_metrics(pairs, 0.5)
    assert got["latency_p50_s"] == pytest.approx(5.5)
    assert got["latency_p95_s"] == pytest.approx(9.55)
    assert m.percentile([], 50) == 0.0


def test_per_kind_and_mode_summary() -> None:
    refuse = item("r", expect="refuse_or_escalate", gold=None, values=(), kind="sensitive")
    pairs = [(item("a"), outcome()), (item("b"), NO_SOURCE), (refuse, NO_SOURCE)]
    assert m.per_kind(pairs) == {"field": {"n": 2, "ok": 1}, "sensitive": {"n": 1, "ok": 1}}
    summary = m.mode_summary(pairs, 0.5)
    assert set(summary) == {
        "hallucination",
        "numeric_fidelity",
        "answer_accuracy",
        "latency_p50_s",
        "latency_p95_s",
        "answered",
    }
    assert summary["answered"] == 1
