"""``POST /v1/coach/ask`` (ADR-007 C6): mapping of ``AskResult``, roles, 503 and privacy."""

from __future__ import annotations

from typing import get_args

import pytest

from ctcv_agent.contracts import AnswerMode, AskDiagnostics, AskResult, ProcedureCard
from ctcv_agent.rag.chunker import chunk_record
from ctcv_agent.rag.types import KnowledgeBaseNotReady, ProcedureNotFound
from ctcv_agent.schemas import SessionContext
from ctcv_api import knowledge
from ctcv_api.schemas import ServedAnswerMode

ASK = "/v1/coach/ask"
FEE_QUESTION = "Đăng ký thường trú mất bao nhiêu tiền?"
PID = "1.004222"
DIAG_MARKER = "diag-marker-never-sent-to-client"
FEE_ANSWER = (
    "Theo Cổng Dịch vụ công - Bộ Công an, đăng ký thường trú nộp trực tiếp 20.000 đồng. "
    "Bác bấm nút xanh có chữ Nguồn để xem trang gốc nhé."
)
NO_SOURCE_LINE = (
    "Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức. "
    "Bác hỏi cán bộ một cửa hoặc tình nguyện viên giúp cháu nhé."
)
SENSITIVE_LINE = (
    "Bác đừng đọc mã OTP, mật khẩu hay số thẻ cho ai, kể cả người xưng là cán bộ. "
    "Nếu thấy lạ, bác hỏi tình nguyện viên hoặc con cháu trước nhé."
)
ASK_OUT_KEYS = {
    "answer",
    "citations",
    "confidence",
    "escalate",
    "refused",
    "reason",
    "answer_mode",
    "procedure",
}


@pytest.fixture
def fee_result(tthc_records) -> AskResult:
    record = tthc_records[PID]
    fee_chunk = next(c for c in chunk_record(record, 1200) if c.section == "phi_le_phi")
    return AskResult(
        answer=FEE_ANSWER,
        citations=[fee_chunk.to_citation("thu 20.000 đồng/lần đăng ký")],
        confidence=0.82,
        escalate=False,
        reason="ok",
        answer_mode="template",
        procedure=ProcedureCard.from_record(record),
        diagnostics=AskDiagnostics(
            intent="phi_le_phi",
            retrieved_procedure_ids=[PID],
            composer_sentence=DIAG_MARKER,
            answer_core=DIAG_MARKER,
            timings_ms={"total": 12.5},
            hosts_contacted=["localhost:11434"],
        ),
    )


def _no_source_result() -> AskResult:
    return AskResult(
        answer=NO_SOURCE_LINE,
        citations=[],
        confidence=0.1,
        escalate=True,
        reason="no_source",
        answer_mode="no_source",
        diagnostics=AskDiagnostics(fallback_reason=DIAG_MARKER),
    )


def _headers_for(make_token, user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token('citizen', user_id)}"}


def test_ask_returns_answer_citations_and_procedure_card(
    client, app, auth_headers, fake_answer_service, fee_result
):
    app.state.answer_service = fake_answer_service(fee_result)
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == ASK_OUT_KEYS
    assert body["answer"] == FEE_ANSWER
    assert (body["reason"], body["answer_mode"], body["refused"]) == ("ok", "template", False)
    assert body["escalate"] is False and body["confidence"] == pytest.approx(0.82)
    citation = body["citations"][0]
    assert citation["procedure_id"] == PID and citation["section"] == "phi_le_phi"
    assert citation["url"].startswith("https://")
    assert citation["agency"] and citation["source_portal"] and citation["fetched_at"]
    assert "effective_date" in citation
    assert citation["quote"] == "thu 20.000 đồng/lần đăng ký"


def test_ask_procedure_card_lists_documents_fees_and_cases(
    client, app, auth_headers, fake_answer_service, fee_result
):
    app.state.answer_service = fake_answer_service(fee_result)
    card = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    card = card.json()["procedure"]
    assert set(card) == {
        "procedure_id",
        "ten",
        "co_quan",
        "source_url",
        "fetched_at",
        "documents",
        "fees",
        "cases",
    }
    assert card["procedure_id"] == PID and card["ten"] == "Đăng ký thường trú"
    assert [doc["doc_key"] for doc in card["documents"]][:2] == ["d01", "d02"]
    assert set(card["documents"][0]) == {
        "doc_key",
        "name",
        "case_label",
        "originals",
        "copies",
        "form_code",
    }
    fee = card["fees"][0]
    assert set(fee) == {"channel", "channel_text", "time_limit", "fee_text", "amounts_vnd"}
    assert (fee["channel"], fee["amounts_vnd"]) == ("truc_tiep", [20000])
    assert len(card["cases"]) == 2


def test_ask_passes_question_and_jwt_identity_to_the_service(
    client, app, make_token, fake_answer_service, fee_result
):
    service = fake_answer_service(fee_result)
    app.state.answer_service = service
    body = {"question": FEE_QUESTION, "session_id": "sess-1"}
    response = client.post(ASK, headers=_headers_for(make_token, "citizen-77"), json=body)
    assert response.status_code == 200
    question, ctx = service.calls[0]
    assert question == FEE_QUESTION
    assert ctx == SessionContext(user_id="citizen-77", role="citizen")


def test_ask_rejects_an_oversized_session_id(
    client, app, auth_headers, fake_answer_service, fee_result
):
    # Red-team F-10 (TL-53): a 200 000-character session_id used to be accepted.
    service = fake_answer_service(fee_result)
    app.state.answer_service = service
    body = {"question": FEE_QUESTION, "session_id": "s" * 65}
    response = client.post(ASK, headers=auth_headers("citizen"), json=body)
    assert response.status_code == 422 and service.calls == []
    ok = client.post(ASK, headers=auth_headers("citizen"), json={**body, "session_id": "s" * 64})
    assert ok.status_code == 200


def test_ask_never_returns_diagnostics(client, app, auth_headers, fake_answer_service, fee_result):
    app.state.answer_service = fake_answer_service(fee_result)
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert "diagnostics" not in response.json()
    assert DIAG_MARKER not in response.text
    assert "localhost:11434" not in response.text


def test_ask_escalates_without_citations_when_no_source(
    client, app, auth_headers, fake_answer_service
):
    app.state.answer_service = fake_answer_service(_no_source_result())
    question = {"question": "Thủ tục đăng ký kết hôn cần những gì?"}
    response = client.post(ASK, headers=auth_headers("citizen"), json=question)
    assert response.status_code == 200
    body = response.json()
    assert body["escalate"] is True and body["citations"] == []
    assert (body["reason"], body["answer_mode"], body["procedure"]) == (
        "no_source",
        "no_source",
        None,
    )
    assert body["answer"] == NO_SOURCE_LINE
    assert DIAG_MARKER not in response.text


def test_ask_safety_refusal_is_reported(client, app, auth_headers, fake_answer_service):
    refusal = AskResult(
        answer=SENSITIVE_LINE,
        confidence=1.0,
        escalate=False,
        refused=True,
        reason="sensitive",
        answer_mode="safety",
    )
    app.state.answer_service = fake_answer_service(refusal)
    question = {"question": "Có người xưng công an gọi xin mã OTP, tôi có đọc không?"}
    body = client.post(ASK, headers=auth_headers("citizen"), json=question).json()
    assert (body["refused"], body["reason"], body["answer_mode"]) == (True, "sensitive", "safety")
    assert body["citations"] == [] and body["procedure"] is None


def test_ask_unverified_llm_mode_is_never_served(client, app, auth_headers, fake_answer_service):
    raw = AskResult(
        answer="Câu thô của mô hình.",
        confidence=0.9,
        escalate=False,
        reason="ok",
        answer_mode="llm_unverified",
    )
    app.state.answer_service = fake_answer_service(raw)
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "ANSWER_FAILED"
    assert "Câu thô" not in response.text


def test_ask_is_503_when_the_knowledge_base_is_not_ready(client, app, auth_headers, monkeypatch):
    app.state.answer_service = None

    def _not_ready():
        raise KnowledgeBaseNotReady("index_missing")

    monkeypatch.setattr(knowledge, "build_services", _not_ready)
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "KB_NOT_READY"
    assert error["message"] == "Kho thủ tục đang được cập nhật, bác thử lại sau ít phút nhé."


def test_ask_retries_the_build_after_a_not_ready_failure(
    client, app, auth_headers, monkeypatch, fake_answer_service, fee_result
):
    app.state.answer_service = None
    service = fake_answer_service(fee_result)
    outcomes: list[object] = [KnowledgeBaseNotReady("index_missing"), service]

    def _build():
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return knowledge.KnowledgeServices(answer=outcome, intake=outcome)

    monkeypatch.setattr(knowledge, "build_services", _build)
    headers = auth_headers("citizen")
    assert client.post(ASK, headers=headers, json={"question": FEE_QUESTION}).status_code == 503
    assert client.post(ASK, headers=headers, json={"question": FEE_QUESTION}).status_code == 200
    assert client.post(ASK, headers=headers, json={"question": FEE_QUESTION}).status_code == 200
    assert len(service.calls) == 2 and outcomes == []


def test_ask_kb_error_raised_while_answering_keeps_its_status(
    client, app, auth_headers, fake_answer_service
):
    app.state.answer_service = fake_answer_service(ProcedureNotFound("unit"))
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROCEDURE_NOT_FOUND"


def test_ask_unexpected_service_error_is_a_generic_500(
    client, app, auth_headers, fake_answer_service
):
    app.state.answer_service = fake_answer_service(RuntimeError("engine exploded"))
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "ANSWER_FAILED"
    assert any(ord(ch) > 127 for ch in error["message"])
    assert "exploded" not in response.text


def test_ask_uses_the_default_offline_service_in_unit_tests(client, auth_headers):
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": FEE_QUESTION})
    assert response.status_code == 503


def test_ask_requires_a_token(client):
    response = client.post(ASK, json={"question": FEE_QUESTION})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("role", ["volunteer", "officer"])
def test_ask_is_forbidden_for_staff_roles(client, auth_headers, role):
    response = client.post(ASK, headers=auth_headers(role), json={"question": FEE_QUESTION})
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "FORBIDDEN"
    assert error["details"]["required"] == ["citizen"]


@pytest.mark.parametrize("question", ["", "x" * 501])
def test_ask_rejects_empty_or_too_long_questions(client, auth_headers, question):
    response = client.post(ASK, headers=auth_headers("citizen"), json={"question": question})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_ask_token_subject_is_the_only_identity(client, app, make_token, fake_answer_service):
    service = fake_answer_service(_no_source_result())
    app.state.answer_service = service
    headers = _headers_for(make_token, "citizen-a")
    body = {"question": FEE_QUESTION, "user_id": "citizen-b"}
    assert client.post(ASK, headers=headers, json=body).status_code == 422
    assert service.calls == []


def test_openapi_documents_the_ask_answer_fields(client):
    spec = client.get("/openapi.json").json()
    operation = spec["paths"][ASK]["post"]
    assert {"401", "403", "422", "503"} <= set(operation["responses"])
    schemas = spec["components"]["schemas"]
    ask_out = schemas["AskOut"]["properties"]
    assert set(ask_out) == ASK_OUT_KEYS
    assert set(schemas["Citation"]["properties"]) >= {
        "agency",
        "source_portal",
        "fetched_at",
        "effective_date",
        "section",
        "procedure_id",
    }


def test_served_modes_are_the_contract_modes_minus_the_eval_only_one():
    assert set(get_args(ServedAnswerMode)) == set(get_args(AnswerMode)) - {"llm_unverified"}
