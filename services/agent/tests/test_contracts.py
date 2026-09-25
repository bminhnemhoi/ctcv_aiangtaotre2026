"""ADR-007 C4: answer and intake contracts shared by the engine (P3), API (P4) and eval (P6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from ctcv_agent.contracts import (
    MAX_CASE_LABEL,
    AnswerMode,
    AnswerService,
    AskDiagnostics,
    AskResult,
    ChecklistItem,
    DocItem,
    FeeItem,
    IntakeRequest,
    IntakeResult,
    IntakeService,
    ProcedureCard,
    ProcedureRef,
    Reason,
)
from ctcv_agent.rag.types import ProcedureRecord
from ctcv_agent.schemas import Citation, SessionContext

RECORDS_DIR = Path(__file__).parent / "fixtures" / "tthc" / "records"
URL = "https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26360"


def _record(pid: str = "1.004222") -> ProcedureRecord:
    return ProcedureRecord.load(RECORDS_DIR / f"{pid}.json")


def _ref(**overrides: Any) -> dict[str, Any]:
    base = {
        "procedure_id": "1.004222",
        "ten": "Đăng ký thường trú",
        "co_quan": "Công an Xã",
        "source_url": URL,
        "fetched_at": "2026-09-24T18:38:59Z",
    }
    base.update(overrides)
    return base


def _citation() -> Citation:
    return Citation(
        doc_id="tthc-1.004222-phi_le_phi-0",
        url=URL,
        title="Đăng ký thường trú — Phí, lệ phí",
        quote="Trực tiếp: Trường hợp công dân nộp hồ sơ trực tiếp thu 20.000 đồng/lần đăng ký",
        agency="Bộ Công an",
        source_portal="Cổng Dịch vụ công - Bộ Công an",
        fetched_at="2026-09-24T18:38:59Z",
        section="phi_le_phi",
        procedure_id="1.004222",
    )


# --------------------------------------------------------------------------- literals


def test_reason_and_answer_mode_values() -> None:
    assert set(get_args(Reason)) == {
        "ok",
        "no_source",
        "sensitive",
        "real_action",
        "pasted_content",
        "verify_failed",
        "kb_not_ready",
    }
    assert set(get_args(AnswerMode)) == {
        "llm_verified",
        "llm_unverified",
        "template",
        "safety",
        "no_source",
    }


# --------------------------------------------------------------------------- intake request


def test_intake_request_accepts_procedure_id_only() -> None:
    req = IntakeRequest(procedure_id="1.004194", received=["d01", "d02"])
    assert req.query is None
    assert req.received == ["d01", "d02"]
    assert req.case_label is None


def test_intake_request_accepts_query_only() -> None:
    req = IntakeRequest(query="  đăng ký tạm trú  ")
    assert req.query == "đăng ký tạm trú"
    assert req.received == []


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"procedure_id": "1.004194", "query": "đăng ký tạm trú"},
        {"procedure_id": None, "query": None},
    ],
)
def test_intake_request_needs_exactly_one_of_procedure_id_and_query(data: dict) -> None:
    with pytest.raises(ValidationError, match="đúng một"):
        IntakeRequest.model_validate(data)


@pytest.mark.parametrize(
    "received",
    [["d1"], ["D01"], ["d001"], ["x01"], ["d01", "d01"], [f"d{i:02d}" for i in range(61)]],
)
def test_intake_request_rejects_bad_received(received: list[str]) -> None:
    with pytest.raises(ValidationError):
        IntakeRequest(procedure_id="1.004194", received=received)


def test_intake_request_accepts_sixty_distinct_keys() -> None:
    keys = [f"d{i:02d}" for i in range(60)]
    assert IntakeRequest(procedure_id="1.004194", received=keys).received == keys


@pytest.mark.parametrize(
    "data",
    [
        {"query": "a"},
        {"query": "a" * 201},
        # v2: case labels follow the record (real ones reach 918 characters, red-team F-09).
        {"procedure_id": "1.004194", "case_label": "x" * (MAX_CASE_LABEL + 1)},
        {"procedure_id": "-bad"},
        {"procedure_id": "1.004194", "user_id": "u-1"},
    ],
)
def test_intake_request_rejects_invalid_fields(data: dict) -> None:
    with pytest.raises(ValidationError):
        IntakeRequest.model_validate(data)


# --------------------------------------------------------------------------- cards


def test_procedure_ref_from_record() -> None:
    ref = ProcedureRef.from_record(_record())
    assert ref.procedure_id == "1.004222"
    assert ref.ten == "Đăng ký thường trú"
    assert ref.co_quan == "Công an Xã"
    assert ref.source_url == URL
    assert ref.fetched_at == _record().meta.fetched_at


def test_procedure_card_from_record_maps_documents_fees_and_cases() -> None:
    record = _record()
    card = ProcedureCard.from_record(record)
    assert [d.doc_key for d in card.documents] == [d.doc_key for d in record.thanh_phan_ho_so]
    first = card.documents[0]
    assert (first.originals, first.copies) == (0, 1)
    assert first.case_label == record.thanh_phan_ho_so[0].truong_hop
    assert card.documents[2].form_code == "CT01"
    assert [f.amounts_vnd for f in card.fees] == [[20000], [10000]]
    assert card.fees[0].channel == "truc_tiep"
    assert card.fees[0].time_limit == "07 Ngày làm việc"
    assert card.cases == list(dict.fromkeys(d.truong_hop for d in record.thanh_phan_ho_so))


def test_procedure_card_without_cases() -> None:
    card = ProcedureCard.from_record(_record("2.000200"))
    assert card.cases == [
        "Trường hợp công dân chưa có thông tin trong cơ sở dữ liệu quốc gia về dân cư thì hồ "
        "sơ còn có"
    ]
    assert all(f.fee_text == "Không" and f.amounts_vnd == [] for f in card.fees)


def test_fee_item_rejects_negative_amounts() -> None:
    with pytest.raises(ValidationError):
        FeeItem(channel="truc_tiep", channel_text="Trực tiếp", amounts_vnd=[-5])


def test_doc_item_rejects_bad_key() -> None:
    with pytest.raises(ValidationError):
        DocItem(doc_key="d1", name="Tờ khai")


# --------------------------------------------------------------------------- ask result


def _ask_result() -> AskResult:
    return AskResult(
        answer="Bác nộp trực tiếp thì mất 20.000 đồng mỗi lần đăng ký. Bác bấm nút xanh có "
        "chữ Nguồn để xem trang gốc nhé.",
        citations=[_citation()],
        confidence=0.82,
        escalate=False,
        reason="ok",
        answer_mode="llm_verified",
        procedure=ProcedureCard.from_record(_record()),
        diagnostics=AskDiagnostics(
            intent="phi_le_phi",
            retrieved_procedure_ids=["1.004222", "1.004194"],
            top_dense=0.71,
            match_score=0.66,
            gate_passed=True,
            answer_core="Bác nộp trực tiếp thì mất 20.000 đồng mỗi lần đăng ký.",
            composer_sentence="Bác nộp trực tiếp thì mất 20.000 đồng mỗi lần đăng ký.",
            composer_doc_ids=["tthc-1.004222-phi_le_phi-0"],
            timings_ms={"retrieve": 120.5, "compose": 900.0, "verify": 3.2, "total": 1030.1},
            hosts_contacted=["localhost:11434"],
        ),
    )


def test_ask_result_json_round_trip() -> None:
    result = _ask_result()
    again = AskResult.model_validate_json(result.model_dump_json())
    assert again == result
    assert again.refused is False
    assert again.citations[0].fetched_at == result.citations[0].fetched_at


def test_ask_result_defaults() -> None:
    result = AskResult(
        answer="Cháu chưa chắc câu này.",
        confidence=0.0,
        escalate=True,
        reason="no_source",
        answer_mode="no_source",
    )
    assert result.citations == []
    assert result.procedure is None
    assert result.diagnostics == AskDiagnostics()
    assert result.diagnostics.degraded is False


@pytest.mark.parametrize(
    ("field", "value"),
    [("confidence", 1.5), ("reason", "maybe"), ("answer_mode", "free"), ("answer", "")],
)
def test_ask_result_rejects_invalid_fields(field: str, value: Any) -> None:
    data = _ask_result().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        AskResult.model_validate(data)


@pytest.mark.parametrize(
    "data",
    [
        {"retrieved_procedure_ids": ["a", "b", "c", "d", "e", "f"]},
        {"retrieved_procedure_ids": ["a", "a"]},
        {"timings_ms": {"sleep": 1.0}},
        {"timings_ms": {"total": -1.0}},
        {"match_score": 1.2},
    ],
)
def test_ask_diagnostics_rejects_invalid(data: dict) -> None:
    with pytest.raises(ValidationError):
        AskDiagnostics.model_validate(data)


# --------------------------------------------------------------------------- intake result


def _items() -> list[ChecklistItem]:
    return [
        ChecklistItem(doc_key="d01", name="Tờ khai thay đổi thông tin cư trú", status="da_nhan"),
        ChecklistItem(doc_key="d02", name="Giấy tờ chứng minh chỗ ở hợp pháp", status="thieu"),
    ]


def _intake(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "procedure": _ref(procedure_id="1.004194", ten="Đăng ký tạm trú"),
        "alternatives": [],
        "cases": ["Hồ sơ đăng ký tạm trú gồm"],
        "needs_case": False,
        "items": [i.model_dump() for i in _items()],
        "missing_count": 1,
        "message_for_citizen": "Bác còn thiếu 1 giấy tờ. Bác xem danh sách bên dưới nhé.",
        "citations": [_citation().model_dump()],
    }
    base.update(overrides)
    return base


def test_intake_result_round_trip() -> None:
    result = IntakeResult.model_validate(_intake())
    assert IntakeResult.model_validate_json(result.model_dump_json()) == result
    assert result.items[1].status == "thieu"


@pytest.mark.parametrize(
    "overrides",
    [
        {"alternatives": [_ref(procedure_id=f"1.00{i}") for i in range(4)]},
        {"missing_count": 2},
        {"message_for_citizen": "Một. Hai. Ba câu."},
        {"message_for_citizen": ""},
        {"items": [{"doc_key": "d01", "name": "Tờ khai", "status": "co"}]},
    ],
)
def test_intake_result_rejects_invalid(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        IntakeResult.model_validate(_intake(**overrides))


def test_checklist_item_extends_doc_item() -> None:
    assert issubclass(ChecklistItem, DocItem)
    assert issubclass(ProcedureCard, ProcedureRef)


# --------------------------------------------------------------------------- protocols


class _Answers:
    def ask(self, question: str, ctx: SessionContext) -> AskResult:
        return _ask_result()


class _Intake:
    def check(self, req: IntakeRequest) -> IntakeResult:
        return IntakeResult.model_validate(_intake())


def test_services_satisfy_protocols() -> None:
    assert isinstance(_Answers(), AnswerService)
    assert isinstance(_Intake(), IntakeService)
    assert not isinstance(object(), AnswerService)
    ctx = SessionContext(user_id="demo-citizen-1")
    assert _Answers().ask("phí bao nhiêu", ctx).reason == "ok"
    assert _Intake().check(IntakeRequest(query="tạm trú")).missing_count == 1
