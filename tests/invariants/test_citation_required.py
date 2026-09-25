"""Invariant (c), brief §15: a factual sentence without a citation is never read out.

``requires_citation`` must reject facts (fees, dates, "theo", "quy định" ...) that no valid
:class:`Citation` backs and accept them once a citation is attached; ``coach.run_turn``
must turn an uncited fact into the "chưa chắc" line plus an escalation.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from ctcv_agent import coach
from ctcv_agent.guardrails import has_factual_claim, requires_citation
from ctcv_agent.planner import Message
from ctcv_agent.schemas import ActionHint, Citation, PlannerOutput, SessionContext, ToolCall
from ctcv_agent.tools.backends import in_memory_backends, sample_turn_state
from ctcv_agent.tools.router import dispatch

FACTUAL = [
    "Theo quy định, xác nhận cư trú không thu lệ phí.",
    "Hạn nộp tờ khai là ngày 30/10/2026.",
    "Lệ phí cấp lại là 50.000 đồng.",
    "Từ ngày 1/3/2026 luật mới có hiệu lực.",
    "Kết quả trả về trong 1 ngày làm việc.",
    "Theo Nghị định 142/2026, mức thu là 0 đồng.",
    "Bác phải nộp trong thời hạn 15 ngày.",
]
NON_FACTUAL = [
    "Bác bấm nút xanh có chữ Quét QR nhé.",
    "Bác muốn chuyển tiền cho con hay trả tiền hàng ạ?",
    "Đó là quảng cáo thôi, bác bấm nút xanh có chữ Quét QR nhé.",
]
CITATION = Citation(
    doc_id="dvc-xac-nhan-cu-tru",
    url="https://dvc.example/huong-dan/xac-nhan-cu-tru",
    title="Hướng dẫn xác nhận thông tin về cư trú",
)
HINT = ActionHint(element_id="btn_qr", color="xanh", label="Quét QR")


class _Scripted:
    def __init__(self, *outputs: PlannerOutput) -> None:
        self._outputs = list(outputs)

    def complete(self, messages: Sequence[Message]) -> PlannerOutput:
        return self._outputs.pop(0)


@pytest.fixture
def run():
    backends = in_memory_backends()
    state = sample_turn_state("sess-demo-1")

    def _run(*outputs: PlannerOutput) -> coach.TurnResult:
        return coach.run_turn(
            state,
            "phí bao nhiêu hả cháu",
            False,
            _Scripted(*outputs),
            lambda call, ctx: dispatch(call, ctx, backends),
            ctx=SessionContext(user_id="u", session_id="sess-demo-1"),
        )

    return _run


@pytest.mark.parametrize("answer", FACTUAL)
def test_factual_sentence_without_citation_is_rejected(answer: str) -> None:
    assert has_factual_claim(answer)
    assert requires_citation(answer, []) is True
    assert requires_citation(answer, None) is True


@pytest.mark.parametrize("answer", FACTUAL)
def test_factual_sentence_with_citation_is_accepted(answer: str) -> None:
    assert requires_citation(answer, [CITATION]) is False
    assert requires_citation(answer, [CITATION.model_dump(mode="json")]) is False


def test_malformed_citation_does_not_count() -> None:
    assert requires_citation(FACTUAL[0], [{"doc_id": "x"}]) is True
    assert requires_citation(FACTUAL[0], [{"doc_id": "x", "url": "ftp://x", "title": "t"}]) is True


@pytest.mark.parametrize("answer", NON_FACTUAL)
def test_non_factual_sentence_needs_no_citation(answer: str) -> None:
    assert not has_factual_claim(answer)
    assert requires_citation(answer, []) is False


def test_coach_blocks_an_uncited_fact_end_to_end(run) -> None:
    result = run(
        PlannerOutput(
            say="Theo quy định, lệ phí là 50.000 đồng. Bác bấm nút xanh có chữ Quét QR nhé.",
            action_hint=HINT,
            confidence=0.9,
        )
    )
    assert result.say == coach.NO_SOURCE and result.escalate
    assert "fact_without_citation" in result.reasons and result.citations == []
    assert result.tool_results[-1].name == "escalate_to_volunteer"


def test_coach_keeps_a_fact_backed_by_verify_citation(run) -> None:
    claim = "Xác nhận cư trú không thu lệ phí, kết quả trả về trong 1 ngày làm việc"
    first = PlannerOutput(
        say="",
        confidence=0.9,
        tool_calls=[
            ToolCall(name="verify_citation", args={"claim": claim, "doc_id": "dvc-xac-nhan-cu-tru"})
        ],
    )
    final = PlannerOutput(
        say=f"{claim}. Bác bấm nút xanh có chữ Quét QR nhé.", action_hint=HINT, confidence=0.9
    )
    result = run(first, final)
    assert result.say == final.say and not result.escalate
    assert [c.doc_id for c in result.citations] == ["dvc-xac-nhan-cu-tru"]
    assert result.citations[0].url.startswith("https://")
