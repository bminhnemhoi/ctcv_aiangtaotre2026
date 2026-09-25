"""IntakeChecker: officer document checklist built from the procedure record (no LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctcv_agent.contracts import IntakeRequest, IntakeResult, IntakeService
from ctcv_agent.guardrails import enforce_style
from ctcv_agent.intake import IntakeChecker
from ctcv_agent.rag.fake import FakeKnowledgeBase
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import DocumentItem, ProcedureNotFound, ProcedureRecord
from ctcv_core.errors import ValidationFailed
from ctcv_core.text import count_sentences

RECORDS_DIR = Path(__file__).parent / "fixtures" / "tthc" / "records"
CCCD_CASE = (
    "Trường hợp công dân chưa có thông tin trong cơ sở dữ liệu quốc gia về dân cư thì hồ sơ còn có"
)
OWNER_CASE = "Trường hợp công dân đăng ký thường trú vào chỗ ở hợp pháp thuộc quyền sở hữu của mình"


@pytest.fixture(scope="module")
def settings() -> RagSettings:
    return load_rag_settings()


@pytest.fixture(scope="module")
def records() -> list[ProcedureRecord]:
    return [ProcedureRecord.load(p) for p in sorted(RECORDS_DIR.glob("*.json"))]


@pytest.fixture
def checker(records: list[ProcedureRecord], settings: RagSettings) -> IntakeChecker:
    return IntakeChecker(FakeKnowledgeBase(records, settings=settings))


def _check(checker: IntakeChecker, **kwargs: object) -> IntakeResult:
    return checker.check(IntakeRequest(**kwargs))


def _assert_message_ok(result: IntakeResult) -> None:
    message = result.message_for_citizen
    assert 1 <= count_sentences(message) <= 2, message
    assert enforce_style(message, first_turn=False, has_action=False).ok, message


def test_checker_satisfies_intake_service(checker: IntakeChecker) -> None:
    assert isinstance(checker, IntakeService)


def test_common_documents_only_when_case_not_chosen(checker: IntakeChecker) -> None:
    result = _check(checker, procedure_id="2.000200", received=["d01"])
    assert result.procedure.procedure_id == "2.000200" and result.alternatives == []
    assert result.cases == [CCCD_CASE] and result.needs_case is True
    assert [(i.doc_key, i.status) for i in result.items] == [("d01", "da_nhan"), ("d04", "thieu")]
    assert result.missing_count == 1
    assert "còn thiếu: Phiếu thu nhận thông tin căn cước" in result.message_for_citizen
    _assert_message_ok(result)


def test_case_label_adds_its_documents_and_complete_file_is_confirmed(
    checker: IntakeChecker,
) -> None:
    result = _check(
        checker,
        procedure_id="2.000200",
        case_label=CCCD_CASE,
        received=["d01", "d02", "d03", "d04"],
    )
    assert result.needs_case is False and result.missing_count == 0
    assert [i.doc_key for i in result.items] == ["d01", "d02", "d03", "d04"]
    assert result.message_for_citizen == (
        "Hồ sơ cấp thẻ Căn cước cho người từ đủ 14 tuổi trở lên thực hiện tại Công an cấp tỉnh "
        "đã đủ giấy tờ theo danh mục, bác chờ cán bộ kiểm tra nội dung nhé."
    )
    _assert_message_ok(result)


def test_missing_list_names_at_most_three_short_documents(checker: IntakeChecker) -> None:
    # v2 (25/9): d02 of this case is "Trường hợp người Việt Nam định cư ở nước ngoài … (mẫu
    # CT02)" — only needed in that sub-case, so it is neu_ap_dung, not missing (orchestrator
    # live test); the message names the two documents every owner needs.
    result = _check(checker, procedure_id="1.004222", case_label=OWNER_CASE, received=[])
    assert result.missing_count == 2 and len(result.items) == 3
    assert [i.status for i in result.items] == ["thieu", "neu_ap_dung", "thieu"]
    message = result.message_for_citizen
    listed = message.split("còn thiếu: ", 1)[1].split(". Bác", 1)[0]
    names = listed.split("; ")
    assert len(names) == 2 and all(len(n) <= 61 for n in names), names
    assert names[0] == "Giấy tờ, tài liệu chứng minh việc sở hữu chỗ ở hợp pháp"
    assert names[1] == "Tờ khai thay đổi thông tin cư trú (mẫu CT01)"
    assert "định cư ở nước ngoài" not in message
    assert message.endswith("Bác bổ sung rồi nộp lại giúp cháu nhé.")
    _assert_message_ok(result)


def test_more_than_three_missing_documents_are_cut_in_the_message(
    records: list[ProcedureRecord], settings: RagSettings
) -> None:
    docs = [DocumentItem(doc_key=f"d0{i}", ten_giay_to=f"Giấy số {i}") for i in range(1, 6)]
    record = records[0].model_copy(update={"thanh_phan_ho_so": docs})
    checker = IntakeChecker(FakeKnowledgeBase([record], settings=settings))
    result = checker.check(IntakeRequest(procedure_id=record.procedure_id))
    assert result.missing_count == 5
    assert "Giấy số 3" in result.message_for_citizen
    assert "Giấy số 4" not in result.message_for_citizen
    _assert_message_ok(result)


def test_case_needed_but_common_documents_complete(checker: IntakeChecker) -> None:
    result = _check(checker, procedure_id="1.004222", received=[])
    assert result.needs_case is True and result.items == [] and result.missing_count == 0
    assert "chọn đúng trường hợp" in result.message_for_citizen
    assert "đã đủ" not in result.message_for_citizen
    _assert_message_ok(result)


def test_query_returns_best_procedure_and_alternatives(checker: IntakeChecker) -> None:
    result = _check(checker, query="đăng ký tạm trú", received=["d01", "d02"])
    assert result.procedure.procedure_id == "1.004194"
    alternatives = [a.procedure_id for a in result.alternatives]
    assert alternatives and "1.004194" not in alternatives and len(alternatives) <= 3


def test_unknown_received_keys_are_ignored(checker: IntakeChecker) -> None:
    result = _check(checker, procedure_id="2.000200", received=["d01", "d04", "d99"])
    assert {i.doc_key for i in result.items} == {"d01", "d04"}
    assert result.missing_count == 0


def test_citations_are_the_document_list_chunks(checker: IntakeChecker) -> None:
    result = _check(checker, procedure_id="1.004222")
    assert result.citations
    for citation in result.citations:
        assert citation.section == "thanh_phan_ho_so" and citation.procedure_id == "1.004222"
        assert citation.url.startswith("https://") and len(citation.quote) <= 300


def test_unknown_procedure_id_is_not_found(checker: IntakeChecker) -> None:
    with pytest.raises(ProcedureNotFound) as exc:
        _check(checker, procedure_id="9.999999")
    assert exc.value.status == 404 and exc.value.code == "PROCEDURE_NOT_FOUND"


def test_query_without_match_is_not_found(checker: IntakeChecker) -> None:
    with pytest.raises(ProcedureNotFound):
        _check(checker, query="zzzz qqqq")


def test_unknown_case_label_is_rejected(checker: IntakeChecker) -> None:
    with pytest.raises(ValidationFailed) as exc:
        _check(checker, procedure_id="2.000200", case_label="Trường hợp không có")
    assert exc.value.status == 422 and exc.value.code == "CASE_NOT_FOUND"


def test_procedure_without_documents(records: list[ProcedureRecord], settings: RagSettings) -> None:
    record = records[0].model_copy(update={"thanh_phan_ho_so": []})
    checker = IntakeChecker(FakeKnowledgeBase([record], settings=settings))
    result = checker.check(IntakeRequest(procedure_id=record.procedure_id))
    assert result.items == [] and result.missing_count == 0 and result.citations == []
    _assert_message_ok(result)


# ----------------------------------------------------------------------------- v2 regressions
def test_conditional_document_received_is_da_nhan_and_never_missing(
    checker: IntakeChecker,
) -> None:
    # Orchestrator live test: received [CT01] for an owner must not report the CT02 form of
    # people settled abroad as missing.
    result = _check(checker, procedure_id="1.004222", case_label=OWNER_CASE, received=["d03"])
    assert [(i.doc_key, i.status) for i in result.items] == [
        ("d01", "thieu"),
        ("d02", "neu_ap_dung"),
        ("d03", "da_nhan"),
    ]
    assert result.missing_count == 1 and "CT02" not in result.message_for_citizen
    both = _check(checker, procedure_id="1.004222", case_label=OWNER_CASE, received=["d02"])
    assert both.items[1].status == "da_nhan"


@pytest.mark.parametrize(
    "name",
    [
        "Trường hợp người nước ngoài thì nộp thêm bản dịch.",
        "Nếu có con dưới 14 tuổi: giấy khai sinh",
        "Đối với Quân đội nhân dân: Giấy giới thiệu của đơn vị.",
        "Riêng người khuyết tật: giấy xác nhận",
    ],
)
def test_names_opening_with_a_case_are_conditional(name: str) -> None:
    from ctcv_agent.intake import is_conditional

    assert is_conditional(DocumentItem(doc_key="d01", ten_giay_to=name))
    assert not is_conditional(DocumentItem(doc_key="d01", ten_giay_to="Tờ khai CT01; đối với trẻ…"))


def test_message_stays_within_two_sentences_with_dotted_long_names(
    records: list[ProcedureRecord], settings: RagSettings
) -> None:
    # Red-team F-09 (real 1.002757): names with inner stops and ellipses made a 3-sentence
    # message, IntakeResult rejected it and the API answered 500.
    names = [
        "Thông tin đề nghị cấp thị thực điện tử (trên Trang thông tin cấp thị thực điện tử hoặc"
        " Cổng dịch vụ công quốc gia) theo mẫu NA1a",
        "Ảnh mới chụp, kích cỡ ảnh 4 x 6cm. Định dạng jpeg… kích thước ≤ 2 MB, mặt nhìn thẳng",
        "Ảnh trang nhân thân hộ chiếu được tải lên Trang thông tin. Theo quy định.",
    ]
    docs = [DocumentItem(doc_key=f"d0{i}", ten_giay_to=n) for i, n in enumerate(names, 1)]
    record = records[0].model_copy(update={"thanh_phan_ho_so": docs})
    checker = IntakeChecker(FakeKnowledgeBase([record], settings=settings))
    result = checker.check(IntakeRequest(procedure_id=record.procedure_id))
    assert result.missing_count == 3
    _assert_message_ok(result)


def test_long_case_label_returned_by_the_checker_is_accepted_back(
    records: list[ProcedureRecord], settings: RagSettings
) -> None:
    # Red-team F-09 (real 1.004222): labels of 408–918 characters came back as cases but the
    # request refused them (max 300), so the officer could not pick the case.
    label = "Đăng ký thường trú tại chỗ ở hợp pháp không thuộc quyền sở hữu, " * 14
    docs = [DocumentItem(doc_key="d01", truong_hop=label.strip(), ten_giay_to="Tờ khai CT01")]
    record = records[0].model_copy(update={"thanh_phan_ho_so": docs})
    checker = IntakeChecker(FakeKnowledgeBase([record], settings=settings))
    first = checker.check(IntakeRequest(procedure_id=record.procedure_id))
    assert len(first.cases[0]) > 800
    chosen = checker.check(
        IntakeRequest(procedure_id=record.procedure_id, case_label=first.cases[0])
    )
    assert chosen.needs_case is False and chosen.missing_count == 1


def test_query_is_redacted_before_search(
    records: list[ProcedureRecord], settings: RagSettings
) -> None:
    seen: list[str] = []

    class Spy(FakeKnowledgeBase):
        def find_procedures(self, query: str, limit: int):  # type: ignore[override]
            seen.append(query)
            return super().find_procedures(query, limit)

    checker = IntakeChecker(Spy(records, settings=settings))
    checker.check(IntakeRequest(query="đăng ký thường trú số 0912345678"))
    assert seen and "0912345678" not in seen[0]
