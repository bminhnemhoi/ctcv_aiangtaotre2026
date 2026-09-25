"""``POST /v1/coach/intake-check`` (ADR-007 C6): officer checklist, roles, 404/422/503."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ctcv_agent.contracts import (
    MAX_CASE_LABEL,
    ChecklistItem,
    DocItem,
    IntakeRequest,
    IntakeResult,
    ProcedureRef,
)
from ctcv_agent.rag.chunker import chunk_record
from ctcv_agent.rag.types import KnowledgeBaseNotReady, ProcedureNotFound
from ctcv_api import knowledge
from ctcv_api.routers import coach as coach_router

INTAKE = "/v1/coach/intake-check"
PID = "2.000200"
ALT_PID = "1.004194"
OUT_KEYS = {
    "procedure",
    "alternatives",
    "cases",
    "needs_case",
    "items",
    "missing_count",
    "message_for_citizen",
    "citations",
}
REF_KEYS = {"procedure_id", "ten", "co_quan", "source_url", "fetched_at"}
ITEM_KEYS = {"doc_key", "name", "case_label", "originals", "copies", "form_code", "status"}


@pytest.fixture
def checklist(tthc_records) -> IntakeResult:
    record = tthc_records[PID]
    general = [d for d in record.thanh_phan_ho_so if d.truong_hop is None]
    items = [
        ChecklistItem(
            **DocItem.from_document(doc).model_dump(),
            status="da_nhan" if doc.doc_key == "d01" else "thieu",
        )
        for doc in general
    ]
    docs_chunk = next(c for c in chunk_record(record, 1200) if c.section == "thanh_phan_ho_so")
    return IntakeResult(
        procedure=ProcedureRef.from_record(record),
        alternatives=[ProcedureRef.from_record(tthc_records[ALT_PID])],
        cases=list(dict.fromkeys(d.truong_hop for d in record.thanh_phan_ho_so if d.truong_hop)),
        needs_case=True,
        items=items,
        missing_count=sum(1 for item in items if item.status == "thieu"),
        message_for_citizen="Hồ sơ còn thiếu một giấy tờ. Bác bổ sung rồi nộp lại giúp cháu nhé.",
        citations=[docs_chunk.to_citation()],
    )


@pytest.mark.parametrize("role", ["volunteer", "officer"])
def test_intake_check_returns_the_checklist_to_staff(
    client, app, auth_headers, fake_intake_service, checklist, role
):
    app.state.intake_service = fake_intake_service(checklist)
    body = {"procedure_id": PID, "received": ["d01"]}
    response = client.post(INTAKE, headers=auth_headers(role), json=body)
    assert response.status_code == 200
    out = response.json()
    assert set(out) == OUT_KEYS
    assert set(out["procedure"]) == REF_KEYS and out["procedure"]["procedure_id"] == PID
    assert [alt["procedure_id"] for alt in out["alternatives"]] == [ALT_PID]
    assert out["needs_case"] is True and len(out["cases"]) == 1
    assert all(set(item) == ITEM_KEYS for item in out["items"])
    statuses = {item["doc_key"]: item["status"] for item in out["items"]}
    assert statuses == {"d01": "da_nhan", "d04": "thieu"}
    assert out["missing_count"] == 1
    assert out["message_for_citizen"].startswith("Hồ sơ còn thiếu")
    assert out["citations"][0]["section"] == "thanh_phan_ho_so"


def test_intake_check_forwards_the_request_unchanged(
    client, app, auth_headers, fake_intake_service, checklist
):
    service = fake_intake_service(checklist)
    app.state.intake_service = service
    body = {"procedure_id": PID, "received": ["d01", "d04"], "case_label": "Trường hợp A"}
    client.post(INTAKE, headers=auth_headers("officer"), json=body)
    assert service.calls == [
        IntakeRequest(procedure_id=PID, received=["d01", "d04"], case_label="Trường hợp A")
    ]


def test_intake_check_accepts_a_free_text_query(
    client, app, auth_headers, fake_intake_service, checklist
):
    service = fake_intake_service(checklist)
    app.state.intake_service = service
    body = {"query": "  làm căn cước  "}
    response = client.post(INTAKE, headers=auth_headers("officer"), json=body)
    assert response.status_code == 200
    assert service.calls == [IntakeRequest(query="làm căn cước")]


def test_intake_check_unknown_procedure_is_404(client, app, auth_headers, fake_intake_service):
    app.state.intake_service = fake_intake_service(ProcedureNotFound("no_match"))
    body = {"query": "đăng ký kết hôn"}
    response = client.post(INTAKE, headers=auth_headers("officer"), json=body)
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "PROCEDURE_NOT_FOUND"
    assert error["message"] == "Chưa tìm thấy thủ tục này trong kho, anh/chị thử gõ tên khác nhé."


@pytest.mark.parametrize(
    "body",
    [
        {"procedure_id": PID, "query": "căn cước"},
        {},
        {"received": ["d01"]},
        {"procedure_id": PID, "received": ["x1"]},
        {"procedure_id": PID, "received": ["d1"]},
        {"procedure_id": PID, "received": ["d001"]},
        {"procedure_id": PID, "received": ["d01", "d01"]},
        {"procedure_id": PID, "received": [f"d{i:02d}" for i in range(61)]},
        # v2: the bound follows the agent contract (real labels reach 918 characters).
        {"procedure_id": PID, "case_label": "x" * (MAX_CASE_LABEL + 1)},
        {"procedure_id": "bad id!"},
        {"query": "a"},
        {"query": "   a   "},
        {"query": "x" * 201},
        {"procedure_id": PID, "user_id": "someone"},
    ],
    ids=[
        "both-targets",
        "no-target",
        "only-received",
        "doc-key-letters",
        "doc-key-one-digit",
        "doc-key-three-digits",
        "duplicate-doc-key",
        "too-many-doc-keys",
        "case-label-too-long",
        "bad-procedure-id",
        "query-too-short",
        "query-too-short-after-strip",
        "query-too-long",
        "unknown-key",
    ],
)
def test_intake_check_rejects_invalid_requests(
    client, app, auth_headers, fake_intake_service, checklist, body
):
    service = fake_intake_service(checklist)
    app.state.intake_service = service
    response = client.post(INTAKE, headers=auth_headers("officer"), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert service.calls == []


def test_intake_check_accepts_sixty_distinct_doc_keys(
    client, app, auth_headers, fake_intake_service, checklist
):
    service = fake_intake_service(checklist)
    app.state.intake_service = service
    received = [f"d{i:02d}" for i in range(60)]
    body = {"procedure_id": PID, "received": received}
    assert client.post(INTAKE, headers=auth_headers("officer"), json=body).status_code == 200
    assert service.calls[0].received == received


def test_stricter_engine_contract_becomes_422_not_500(
    client, app, auth_headers, fake_intake_service, checklist, monkeypatch
):
    class _RejectEverything(BaseModel):
        never_present: int

    service = fake_intake_service(checklist)
    app.state.intake_service = service
    monkeypatch.setattr(coach_router, "IntakeRequest", _RejectEverything)
    response = client.post(INTAKE, headers=auth_headers("officer"), json={"procedure_id": PID})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert PID not in response.text
    assert service.calls == []


def test_intake_check_is_503_when_the_knowledge_base_is_not_ready(
    client, app, auth_headers, monkeypatch
):
    app.state.intake_service = None

    def _not_ready():
        raise KnowledgeBaseNotReady("index_missing")

    monkeypatch.setattr(knowledge, "build_services", _not_ready)
    response = client.post(INTAKE, headers=auth_headers("officer"), json={"procedure_id": PID})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "KB_NOT_READY"


def test_intake_check_unexpected_error_is_a_generic_500(
    client, app, auth_headers, fake_intake_service
):
    app.state.intake_service = fake_intake_service(ValueError("checker exploded"))
    response = client.post(INTAKE, headers=auth_headers("officer"), json={"procedure_id": PID})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTAKE_FAILED"
    assert "exploded" not in response.text


def test_intake_check_requires_a_token(client):
    response = client.post(INTAKE, json={"procedure_id": PID})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_intake_check_is_forbidden_for_citizens(client, auth_headers):
    response = client.post(INTAKE, headers=auth_headers("citizen"), json={"procedure_id": PID})
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "FORBIDDEN"
    assert error["details"]["required"] == ["officer", "volunteer"]


def test_openapi_documents_intake_check(client):
    spec = client.get("/openapi.json").json()
    operation = spec["paths"][INTAKE]["post"]
    assert {"200", "401", "403", "404", "422", "503"} <= set(operation["responses"])
    schemas = spec["components"]["schemas"]
    assert set(schemas["IntakeCheckOut"]["properties"]) == OUT_KEYS
    assert set(schemas["IntakeCheckIn"]["properties"]) == {
        "procedure_id",
        "query",
        "received",
        "case_label",
    }
