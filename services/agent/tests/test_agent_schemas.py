"""PlannerOutput and friends parse strictly (brief §7, epic E05 "parse chặt")."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctcv_agent.schemas import (
    RED_FLAG_CODES,
    SIDE_EFFECTS,
    ActionHint,
    Citation,
    PlannerOutput,
    SessionContext,
    ToolCall,
    TurnResult,
)


def test_planner_output_minimal() -> None:
    out = PlannerOutput(say="Bác bấm nút xanh có chữ Quét QR nhé.", confidence=0.9)
    assert out.action_hint is None
    assert out.tool_calls == []


def test_planner_output_full() -> None:
    out = PlannerOutput.model_validate(
        {
            "say": "Bác bấm nút xanh có chữ Quét QR nhé.",
            "action_hint": {"element_id": "btn_qr", "color": "xanh", "label": "Quét QR"},
            "tool_calls": [{"name": "next_step", "args": {"session_id": "sess-demo-1"}}],
            "confidence": 0.85,
        }
    )
    assert out.action_hint == ActionHint(element_id="btn_qr", color="xanh", label="Quét QR")
    assert out.tool_calls[0].name == "next_step"


@pytest.mark.parametrize(
    "payload",
    [
        {"say": "x", "confidence": 1.5},
        {"say": "x", "confidence": -0.1},
        {"say": "x", "confidence": 0.5, "extra": 1},
        {
            "say": "x",
            "confidence": 0.5,
            "action_hint": {"element_id": "Btn", "color": "xanh", "label": "A"},
        },
        {"say": "x", "confidence": 0.5, "tool_calls": [{"name": "Send Money", "args": {}}]},
        {"confidence": 0.5},
    ],
)
def test_planner_output_rejects(payload: dict) -> None:
    with pytest.raises(ValidationError):
        PlannerOutput.model_validate(payload)


def test_tool_call_args_default_and_forbid_extra() -> None:
    assert ToolCall(name="next_step").args == {}
    with pytest.raises(ValidationError):
        ToolCall(name="next_step", extra=1)  # type: ignore[call-arg]


def test_citation_requires_http_url() -> None:
    Citation(doc_id="d1", url="https://dvc.example/a", title="A")
    with pytest.raises(ValidationError):
        Citation(doc_id="d1", url="ftp://x", title="A")


def test_session_context_is_frozen_and_has_no_pii_fields() -> None:
    ctx = SessionContext(user_id="u1")
    with pytest.raises(ValidationError):
        ctx.user_id = "u2"  # type: ignore[misc]
    assert not {"phone", "cccd", "email", "otp"} & set(SessionContext.model_fields)


def test_turn_result_defaults() -> None:
    result = TurnResult(say="ok")
    assert result.escalate is False and result.refused is False and result.citations == []


def test_enums_match_brief() -> None:
    assert set(RED_FLAG_CODES) == {
        "giuc-chuyen-tien",
        "doi-otp",
        "xung-co-quan",
        "link-la",
        "doa-dam",
        "yeu-cau-cai-app",
        "giu-bi-mat",
        "tai-khoan-la",
    }
    assert SIDE_EFFECTS == {"none", "sandbox", "log"}
