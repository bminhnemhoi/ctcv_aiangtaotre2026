"""Deterministic answer sentences built only from record fields (no derived numbers)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctcv_agent.answer_templates import (
    CLOSING_DEFAULT,
    CLOSING_DOCS,
    FIXED_LINES,
    NO_SOURCE_LINE,
    PASTED_LINE,
    REAL_ACTION_LINE,
    SENSITIVE_LINE,
    TemplateAnswer,
    citation_quote,
    claims_free,
    clip_words,
    closing_for,
    common_documents,
    document_condition,
    fee_channel_mismatch,
    fee_status,
    limit_sentences,
    lower_first,
    one_sentence,
    render_template,
    replace_banned_terms,
    short_doc_name,
)
from ctcv_agent.guardrails import enforce_style
from ctcv_agent.numeric import canonical_numbers, numbers_supported
from ctcv_agent.rag.chunker import chunk_record
from ctcv_agent.rag.types import CachThuc, DocumentItem, FormRef, LegalRef, ProcedureRecord
from ctcv_core.text import count_sentences

RECORDS_DIR = Path(__file__).parent / "fixtures" / "tthc" / "records"
PORTAL = "Cổng Dịch vụ công - Bộ Công an"
INTENTS = (
    "phi_le_phi",
    "thoi_han",
    "thanh_phan_ho_so",
    "noi_nop",
    "bieu_mau",
    "dieu_kien",
    "can_cu_phap_ly",
    "trinh_tu",
    "tong_quan",
)


@pytest.fixture(scope="module")
def records() -> dict[str, ProcedureRecord]:
    loaded = [ProcedureRecord.load(p) for p in sorted(RECORDS_DIR.glob("*.json"))]
    return {r.procedure_id: r for r in loaded}


def _render(intent: str, record: ProcedureRecord) -> TemplateAnswer | None:
    return render_template(intent, record, PORTAL)


def _assert_speakable(sentence: str) -> None:
    assert count_sentences(sentence) == 1, sentence
    verdict = enforce_style(sentence, first_turn=False, has_action=False)
    assert verdict.ok, (sentence, verdict.reasons)
    assert sentence.startswith(f"Theo {PORTAL}, ") and sentence.endswith(".")


# ----------------------------------------------------------------------------- fixed lines
@pytest.mark.parametrize("line", FIXED_LINES)
def test_fixed_lines_pass_style_and_have_at_most_two_sentences(line: str) -> None:
    verdict = enforce_style(line, first_turn=False, has_action=False)
    assert verdict.ok, verdict.reasons
    assert 1 <= count_sentences(line) <= 2


def test_fixed_lines_are_the_contract_texts() -> None:
    assert NO_SOURCE_LINE == (
        "Cháu chưa chắc câu này vì chưa tìm thấy trong giấy tờ chính thức. "
        "Bác hỏi cán bộ một cửa hoặc tình nguyện viên giúp cháu nhé."
    )
    assert SENSITIVE_LINE.startswith("Bác đừng đọc mã OTP")
    assert REAL_ACTION_LINE.startswith("Cháu không làm thay bác")
    assert PASTED_LINE.startswith("Nội dung này giống tin nhắn")
    assert CLOSING_DEFAULT == "Bác bấm nút xanh có chữ Nguồn để xem trang gốc nhé."
    assert CLOSING_DOCS == "Bác xem thẻ Giấy tờ cần chuẩn bị ngay bên dưới nhé."
    assert len(FIXED_LINES) == 6


def test_closing_depends_on_intent() -> None:
    assert closing_for("thanh_phan_ho_so") == CLOSING_DOCS
    assert closing_for("phi_le_phi") == CLOSING_DEFAULT
    assert closing_for("tong_quan") == CLOSING_DEFAULT


# ----------------------------------------------------------------------------- every intent
@pytest.mark.parametrize("intent", INTENTS)
@pytest.mark.parametrize("pid", ["1.004222", "2.000200", "1.004194"])
def test_every_template_is_one_styled_sentence_with_source_numbers_only(
    intent: str, pid: str, records: dict[str, ProcedureRecord]
) -> None:
    record = records[pid]
    answer = _render(intent, record)
    if answer is None:
        return
    _assert_speakable(answer.sentence)
    chunks = [c for c in chunk_record(record, 1200) if c.section in answer.sections]
    assert chunks, answer.sections
    check = numbers_supported(answer.sentence, [c.text for c in chunks])
    assert check.ok, (answer.sentence, check.unsupported)


def test_fee_lists_each_channel_amount(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("phi_le_phi", records["1.004222"])
    assert answer is not None and answer.sections == ("phi_le_phi",)
    assert "nộp trực tiếp 20.000 đồng" in answer.sentence
    assert "nộp trực tuyến 10.000 đồng" in answer.sentence
    assert "đăng ký thường trú" in answer.sentence


def test_fee_marked_none_says_free(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("phi_le_phi", records["2.000200"])
    assert answer is not None
    assert "không thu phí, lệ phí" in answer.sentence


def test_fee_without_information_gives_none(records: dict[str, ProcedureRecord]) -> None:
    assert _render("phi_le_phi", records["1.004194"]) is None


def test_fee_uses_at_most_two_channels_and_joins_several_amounts(
    records: dict[str, ProcedureRecord],
) -> None:
    channels = [
        CachThuc(
            kenh="truc_tiep", kenh_text="Trực tiếp", phi_le_phi="50.000 đồng", phi_vnd=[50000]
        ),
        CachThuc(
            kenh="truc_tuyen",
            kenh_text="Trực tuyến",
            phi_le_phi="25.000 hoặc 30.000 đồng",
            phi_vnd=[25000, 30000],
        ),
        CachThuc(
            kenh="buu_chinh", kenh_text="Bưu chính", phi_le_phi="70.000 đồng", phi_vnd=[70000]
        ),
    ]
    record = records["1.004222"].model_copy(update={"cach_thuc": channels})
    answer = _render("phi_le_phi", record)
    assert answer is not None
    assert "25.000 đồng hoặc 30.000 đồng" in answer.sentence
    assert "70.000" not in answer.sentence


def test_fee_text_without_amount_is_quoted(records: dict[str, ProcedureRecord]) -> None:
    channels = [CachThuc(kenh="truc_tiep", kenh_text="Trực tiếp", phi_le_phi="Theo quy định")]
    record = records["1.004222"].model_copy(update={"cach_thuc": channels})
    answer = _render("phi_le_phi", record)
    assert answer is not None and "“Theo quy định”" in answer.sentence


PASSPORT_FEE = (
    "160.000/hộ chiếu, trường hợp cấp lại do bị hư hỏng hoặc bị mất: 320.000đ/hộ chiếu "
    "(áp dụng đến hết ngày 31/12/2023)"
)
MISTYPED_FEE = "Lệ phí : 25.000 Đồng (25.000.000đ/giấy thông hành)"


def _channel(text: str | None, amounts: list[int], kenh: str = "truc_tiep") -> CachThuc:
    label = {"truc_tiep": "Trực tiếp", "truc_tuyen": "Trực tuyến"}[kenh]
    return CachThuc(kenh=kenh, kenh_text=label, phi_le_phi=text, phi_vnd=amounts)


def _with_fees(record: ProcedureRecord, *channels: CachThuc) -> ProcedureRecord:
    return record.model_copy(update={"cach_thuc": list(channels)})


def test_fee_status_classifies_the_fee_wording(records: dict[str, ProcedureRecord]) -> None:
    base = records["1.004222"]
    assert fee_status(base) == "stated"
    assert fee_status(records["2.000200"]) == "free"
    assert fee_status(records["1.004194"]) == "unknown"  # real case: "Phí: 1" → null
    assert fee_status(_with_fees(base, _channel(PASSPORT_FEE, [320000]))) == "quoted"
    assert fee_status(_with_fees(base, _channel("Chưa quy định.", []))) == "quoted"
    assert fee_status(_with_fees(base, _channel(MISTYPED_FEE, [25000, 25000000]))) == "suspicious"
    assert fee_status(_with_fees(base, _channel("Theo biểu phí", [30000]))) == "suspicious"
    free_and_unknown = _with_fees(base, _channel("Không", []), _channel(None, [], "truc_tuyen"))
    assert fee_status(free_and_unknown) == "stated"


def test_amounts_missing_from_the_fee_text_are_quoted_not_stated(
    records: dict[str, ProcedureRecord],
) -> None:
    # Real record 1.001456: phi_vnd kept only 320.000 (re-issue after loss) — stating it as
    # "the" fee would be wrong, so the source wording is quoted.
    answer = _render(
        "phi_le_phi", _with_fees(records["1.004222"], _channel(PASSPORT_FEE, [320000]))
    )
    assert answer is not None and answer.uncertain is False
    assert "ghi “160.000/hộ chiếu, trường hợp cấp lại" in answer.sentence
    assert "là nộp trực tiếp 320.000 đồng" not in answer.sentence


def test_mistyped_fee_states_no_amount_and_is_uncertain(
    records: dict[str, ProcedureRecord],
) -> None:
    record = _with_fees(records["1.004222"], _channel(MISTYPED_FEE, [25000, 25000000]))
    answer = _render("phi_le_phi", record)
    assert answer is not None and answer.uncertain is True
    assert answer.sections == ("phi_le_phi",)
    assert canonical_numbers(answer.sentence) <= canonical_numbers(record.ten)
    assert "chưa đọc chắc được con số" in answer.sentence
    _assert_speakable(answer.sentence)


def test_free_is_said_only_when_every_channel_says_none(
    records: dict[str, ProcedureRecord],
) -> None:
    record = _with_fees(
        records["1.004222"], _channel("Không", []), _channel(None, [], "truc_tuyen")
    )
    answer = _render("phi_le_phi", record)
    assert answer is not None
    assert "nộp trực tiếp không thu phí" in answer.sentence
    assert "không thu phí, lệ phí" not in answer.sentence
    assert "trực tuyến" not in answer.sentence


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("Đăng ký tạm trú miễn phí bác nhé.", True),
        ("Thủ tục này không mất tiền đâu bác.", True),
        ("Bác không phải nộp lệ phí gì cả.", True),
        ("Thủ tục này không thu lệ phí.", True),
        ("Lệ phí hộ chiếu là 0 đồng.", True),
        ("Bác nộp trực tiếp 20.000 đồng.", False),
        ("Bác không cần mang giấy tờ gì thêm.", False),
    ],
)
def test_claims_free_spots_every_way_of_saying_free(sentence: str, expected: bool) -> None:
    assert claims_free(sentence) is expected


def test_fee_channel_mismatch_catches_swapped_amounts(records: dict[str, ProcedureRecord]) -> None:
    record = records["1.004222"]  # trực tiếp 20.000, trực tuyến 10.000
    good = "Bác nộp trực tiếp thì mất 20.000 đồng, còn nộp trực tuyến thì mất 10.000 đồng."
    swapped = "Bác nộp trực tiếp thì mất 10.000 đồng, còn nộp trực tuyến thì mất 20.000 đồng."
    online_words = "Nộp qua mạng mất 20.000 đồng."
    assert fee_channel_mismatch(good, record) is False
    assert fee_channel_mismatch(swapped, record) is True
    assert fee_channel_mismatch(online_words, record) is True
    assert fee_channel_mismatch("Lệ phí là 20.000 đồng.", record) is False
    assert fee_channel_mismatch("Bác nộp trực tiếp nhé.", record) is False


def test_time_limit_shared_by_channels_is_said_once(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("thoi_han", records["1.004222"])
    assert answer is not None and answer.sections == ("thoi_han",)
    assert answer.sentence.count("07 Ngày làm việc") == 1


def test_time_limit_per_channel(records: dict[str, ProcedureRecord]) -> None:
    channels = [
        CachThuc(kenh="truc_tiep", kenh_text="Trực tiếp", thoi_han="07 ngày làm việc"),
        CachThuc(kenh="truc_tuyen", kenh_text="Trực tuyến", thoi_han="05 ngày làm việc"),
    ]
    record = records["1.004222"].model_copy(update={"cach_thuc": channels})
    answer = _render("thoi_han", record)
    assert answer is not None
    assert "nộp trực tiếp 07 ngày làm việc" in answer.sentence
    assert "nộp trực tuyến 05 ngày làm việc" in answer.sentence


def test_where_to_submit_names_the_agency(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("noi_nop", records["1.004222"])
    assert answer is not None and answer.sections == ("tong_quan",)
    assert "Công an Xã" in answer.sentence and "trực tiếp hoặc trực tuyến" in answer.sentence


def test_documents_template_names_the_first_common_document(
    records: dict[str, ProcedureRecord],
) -> None:
    answer = _render("thanh_phan_ho_so", records["2.000200"])
    assert answer is not None and answer.sections == ("thanh_phan_ho_so",)
    assert "cần chuẩn bị các giấy tờ trong danh mục thủ tục, trong đó có" in answer.sentence
    assert "Phiếu đề nghị giải quyết thủ tục về căn cước" in answer.sentence
    assert "(" not in answer.sentence.split("trong đó có", 1)[1]


def test_documents_template_counts_nothing(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("thanh_phan_ho_so", records["1.004222"])
    assert answer is not None
    tail = answer.sentence.split("trong đó có", 1)[1]
    assert not any(ch.isdigit() for ch in tail.replace("CT01", ""))
    assert "6 giấy" not in answer.sentence and "sáu" not in answer.sentence


def test_forms_come_from_bieu_mau_then_from_documents(records: dict[str, ProcedureRecord]) -> None:
    from_docs = _render("bieu_mau", records["1.004222"])
    assert from_docs is not None and from_docs.sections == ("thanh_phan_ho_so",)
    assert "CT01" in from_docs.sentence  # the form most documents use
    forms = [FormRef(ten="Tờ khai CT01", url="https://example.gov.vn/ct01.docx")]
    record = records["1.004222"].model_copy(update={"bieu_mau": forms})
    from_forms = _render("bieu_mau", record)
    assert from_forms is not None and from_forms.sections == ("bieu_mau",)
    assert "Tờ khai CT01" in from_forms.sentence
    bare = records["1.004222"].model_copy(update={"thanh_phan_ho_so": [], "bieu_mau": []})
    assert _render("bieu_mau", bare) is None


def test_conditions(records: dict[str, ProcedureRecord]) -> None:
    none = _render("dieu_kien", records["2.000200"])
    assert none is not None and "không nêu yêu cầu, điều kiện riêng" in none.sentence
    record = records["2.000200"].model_copy(
        update={"yeu_cau_dieu_kien": "Công dân từ đủ 14 tuổi. Có mặt trực tiếp."}
    )
    stated = _render("dieu_kien", record)
    assert stated is not None and "Công dân từ đủ 14 tuổi; Có mặt trực tiếp" in stated.sentence
    empty = records["2.000200"].model_copy(update={"yeu_cau_dieu_kien": None})
    assert _render("dieu_kien", empty) is None


def test_legal_basis_names_at_most_two_documents(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("can_cu_phap_ly", records["1.004222"])
    assert answer is not None and answer.sections == ("can_cu_phap_ly",)
    assert "Luật 68/2020/QH14" in answer.sentence and "Nghị định 62/2021/NĐ-CP" in answer.sentence
    assert "55/2021" not in answer.sentence
    one = records["1.004222"].model_copy(update={"can_cu_phap_ly": [LegalRef(ten="Luật Cư trú")]})
    single = _render("can_cu_phap_ly", one)
    assert single is not None and "Luật Cư trú" in single.sentence
    none = records["1.004222"].model_copy(update={"can_cu_phap_ly": []})
    assert _render("can_cu_phap_ly", none) is None


def test_first_step_is_cut_on_a_word_boundary(records: dict[str, ProcedureRecord]) -> None:
    answer = _render("trinh_tu", records["2.000200"])
    assert answer is not None and answer.sections == ("trinh_tu",)
    step = answer.sentence.split("bước đầu là ", 1)[1]
    assert len(step) <= 162 and step.endswith("….")
    assert "Bước 1" not in step


def test_overview_falls_back_to_where_to_submit(records: dict[str, ProcedureRecord]) -> None:
    record = records["1.004222"].model_copy(update={"trinh_tu": []})
    answer = _render("tong_quan", record)
    assert answer is not None and answer.sections == ("tong_quan",)
    assert _render("trinh_tu", record) is None


def test_unknown_intent_renders_overview(records: dict[str, ProcedureRecord]) -> None:
    assert _render("khong_ton_tai", records["1.004222"]) == _render(
        "tong_quan", records["1.004222"]
    )


def test_banned_terms_in_source_are_replaced(records: dict[str, ProcedureRecord]) -> None:
    record = records["1.004222"].model_copy(
        update={"trinh_tu": ["Bước 1: Công dân xác thực tài khoản trên giao diện của cổng."]}
    )
    answer = _render("trinh_tu", record)
    assert answer is not None
    assert "kiểm tra tài khoản trên màn hình" in answer.sentence


def test_document_without_common_item_names_no_document(
    records: dict[str, ProcedureRecord],
) -> None:
    # Was "…, trong đó có Giấy A." (first document): live check 25/9 showed that naming a
    # document needed only in some case reads as "always needed"; the card lists them all.
    docs = [DocumentItem(doc_key="d01", truong_hop="Trường hợp A", ten_giay_to="Giấy A. Kèm B")]
    record = records["1.004222"].model_copy(update={"thanh_phan_ho_so": docs})
    answer = _render("thanh_phan_ho_so", record)
    assert answer is not None
    # v2 (25/9): worded with the chunk's own words so the citation check supports it.
    assert answer.sentence.endswith("gồm các thành phần tùy từng trường hợp.")
    assert "Giấy A" not in answer.sentence


def test_document_sentence_without_common_item_is_supported_by_its_chunk(
    records: dict[str, ProcedureRecord],
) -> None:
    # Dev item g-1.003677-giayto (Khai báo tạm vắng): every document has a case; the old
    # sentence scored 0.42 lexical support against its chunk (hallucination metric).
    from ctcv_agent.rag.chunker import chunk_record
    from ctcv_agent.verify import evaluate_sentence

    docs = [
        DocumentItem(doc_key="d01", truong_hop="Trường hợp công dân thuộc điểm a, hồ sơ gồm",
                     ten_giay_to="Đề nghị khai báo tạm vắng;"),
        DocumentItem(doc_key="d02", truong_hop="Trường hợp thuộc điểm c",
                     ten_giay_to="Nội dung khai báo tạm vắng gồm: họ và tên"),
    ]  # fmt: skip
    record = records["1.004222"].model_copy(
        update={"ten": "Khai báo tạm vắng", "thanh_phan_ho_so": docs}
    )
    answer = _render("thanh_phan_ho_so", record)
    assert answer is not None
    chunks = [c.text for c in chunk_record(record, 1200) if c.section == "thanh_phan_ho_so"]
    assert evaluate_sentence(answer.sentence, chunks, 0.5).ok


def test_common_documents_are_the_ones_listed_under_every_case(
    records: dict[str, ProcedureRecord],
) -> None:
    # 1.004222: every document sits under a case heading; CT01 is under each of them.
    assert [d.doc_key for d in common_documents(records["1.004222"])] == ["d03", "d06"]
    assert [d.doc_key for d in common_documents(records["2.000200"])] == ["d01", "d04"]
    one_case = [
        DocumentItem(doc_key="d01", truong_hop="Trường hợp A", ten_giay_to="Tờ khai", mau="CT01")
    ]
    single = records["1.004222"].model_copy(update={"thanh_phan_ho_so": one_case})
    assert common_documents(single) == []


def test_short_doc_name_drops_an_unclosed_aside() -> None:
    name = "Tờ khai đề nghị cấp hộ chiếu (mẫu TK01 dành cho người từ 14 tuổi; mẫu TK01a) ban hành"
    assert short_doc_name(name, 120) == "Tờ khai đề nghị cấp hộ chiếu"


def test_document_condition_reads_the_case_column_and_inline_conditions() -> None:
    case = "Trường hợp công dân chưa có thông tin trong cơ sở dữ liệu quốc gia về dân cư"
    by_case = DocumentItem(doc_key="d02", truong_hop=case, ten_giay_to="Giấy tờ pháp lý")
    assert document_condition(by_case) == ("Giấy tờ pháp lý", case)
    inline = DocumentItem(
        doc_key="d01",
        ten_giay_to=(
            "Bản sao giấy khai sinh hoặc trích lục giấy khai sinh đối với người chưa đủ 14 tuổi "
            "chưa được cấp mã số định danh cá nhân; nếu là bản chụp thì xuất trình bản chính"
        ),
    )
    assert document_condition(inline) == (
        "Bản sao giấy khai sinh hoặc trích lục giấy khai sinh",
        "đối với người chưa đủ 14 tuổi chưa được cấp mã số định danh cá nhân",
    )
    optional = DocumentItem(doc_key="d01", ten_giay_to="Giấy chứng minh nhân dân 09 số (nếu có).")
    assert document_condition(optional) == ("Giấy chứng minh nhân dân 09 số", "nếu có")


def test_document_condition_keeps_notes_of_the_case_column() -> None:
    # Real records 2.000200 / 1.001247: CC01 is printed by the officer at intake (the note
    # says so); "bác cần mang CC01" without it is wrong. A column repeating the name is empty.
    name = "Phiếu thu nhận thông tin căn cước (Mẫu CC01)"
    note_text = "Phiếu được tạo lập khi trích xuất thông tin để công dân ký xác nhận"
    note = DocumentItem(doc_key="d04", truong_hop=note_text, ten_giay_to=name)
    same = DocumentItem(doc_key="d01", truong_hop=name, ten_giay_to=name)
    assert document_condition(note) == (name, note_text)
    assert document_condition(same) == (name, None)
    # Real 2.000200 d01: the column is the name plus a description of the form.
    described = f"{name}. Phiếu này là biểu mẫu điện tử, công dân kê khai khi nộp trực tuyến"
    form = DocumentItem(doc_key="d01", truong_hop=described, ten_giay_to=name)
    assert document_condition(form) == (name, None)
    leading = DocumentItem(
        doc_key="d04", ten_giay_to="Trường hợp nộp trực tuyến thì phải chứng thực"
    )
    assert document_condition(leading) == (leading.ten_giay_to, leading.ten_giay_to)


def test_document_condition_case_that_ends_with_the_name_is_a_case() -> None:
    # Real record 2.001194 d03: the case sentence ends with the document name itself.
    name = "Giấy tờ chứng minh là người đại diện hợp pháp của người dưới 14 tuổi"
    case = f"Trường hợp người đề nghị là người đại diện thì hồ sơ phải có {name.lower()}."
    doc = DocumentItem(doc_key="d03", truong_hop=case, ten_giay_to=name)
    assert document_condition(doc) == (name, case)


def test_document_condition_reads_only_the_first_sentence_of_the_name() -> None:
    # Real record 1.001456 (hộ chiếu): the second sentence says who signs, not when needed.
    name = (
        "Tờ khai đề nghị cấp hộ chiếu (mẫu TK01 dành cho người từ 14 tuổi trở lên; mẫu TK01a) "
        "ban hành kèm theo Thông tư số 31/2023/TT-BCA. Đối với người chưa đủ 14 tuổi thì "
        "người đại diện hợp pháp khai và ký thay."
    )
    assert document_condition(DocumentItem(doc_key="d05", ten_giay_to=name)) == (name, None)


def test_documents_template_prefers_a_document_needed_in_every_case(
    records: dict[str, ProcedureRecord],
) -> None:
    # Live check 25/9 (hộ chiếu): the first document is only for children under 14.
    docs = [
        DocumentItem(
            doc_key="d01", ten_giay_to="Bản sao giấy khai sinh đối với người chưa đủ 14 tuổi"
        ),
        DocumentItem(doc_key="d02", truong_hop="Trường hợp bị mất", ten_giay_to="Đơn trình báo"),
        DocumentItem(
            doc_key="d03",
            truong_hop="Tờ khai đề nghị cấp hộ chiếu (mẫu TK01)",
            ten_giay_to="Tờ khai đề nghị cấp hộ chiếu (mẫu TK01)",
        ),
    ]
    record = records["1.004222"].model_copy(update={"thanh_phan_ho_so": docs})
    answer = _render("thanh_phan_ho_so", record)
    assert answer is not None and answer.sentence.endswith(
        "trong đó có Tờ khai đề nghị cấp hộ chiếu."
    )


def test_one_sentence_helper() -> None:
    assert one_sentence("  Bước một. Bước hai!  Xong?  ") == "Bước một; Bước hai; Xong."
    assert one_sentence("Phí 20.000 đồng") == "Phí 20.000 đồng."
    assert one_sentence("...") == ""


def test_replace_banned_terms_keeps_case_of_the_rest() -> None:
    assert replace_banned_terms("Bấm Menu rồi chọn Tab") == "Bấm danh sách rồi chọn thẻ"
    assert replace_banned_terms("không có gì") == "không có gì"


def test_clipped_name_before_a_lowercase_word_stays_one_clause() -> None:
    assert one_sentence("có Nghị quyết dài… và Luật Căn cước") == (
        "có Nghị quyết dài… và Luật Căn cước."
    )
    assert one_sentence("có Nghị quyết dài… Luật Căn cước") == "có Nghị quyết dài…, Luật Căn cước."


def test_clip_never_leaves_an_open_parenthesis() -> None:
    text = "Công dân đến cơ quan quản lý căn cước của Công an cấp tỉnh (Phòng Cảnh sát quản lý)"
    clipped = clip_words(text, 75)
    assert "(" not in clipped and clipped.endswith("tỉnh…")


def test_short_doc_name_keeps_meaningful_asides() -> None:
    assert short_doc_name("Giấy khai sinh (nếu có)", 60) == "Giấy khai sinh (nếu có)"
    assert short_doc_name("Tờ khai (Mẫu CT01 ban hành kèm theo Thông tư 66)", 60) == "Tờ khai"


def test_text_helpers_edge_cases() -> None:
    assert lower_first("CMND hết hạn") == "CMND hết hạn"
    assert lower_first("Đăng ký") == "đăng ký"
    assert clip_words("x" * 30, 10) == "x" * 9 + "…"
    assert citation_quote("") == ""
    assert limit_sentences("Một. Hai. Ba.", 2) == "Một. Hai."
    assert limit_sentences("Một câu.", 2) == "Một câu."


def test_long_single_line_quote_is_cut_to_two_sentences_and_300_chars() -> None:
    line = " ".join(f"Câu số {i} nói về thủ tục đăng ký thường trú." for i in range(20))
    quote = citation_quote(line, "đăng ký")
    assert len(quote) <= 300 and count_sentences(quote) <= 2 and quote.startswith("Câu số 0")


def test_quote_prefers_lines_with_the_answer_numbers() -> None:
    lines = ["Dòng đầu " + "x" * 280, "Trực tuyến: thu 10.000 đồng", "Dòng cuối"]
    text = chr(10).join(lines)
    quote = citation_quote(text, "mất 10.000 đồng")
    assert quote == "Trực tuyến: thu 10.000 đồng Dòng cuối"
    assert citation_quote(text).startswith("Dòng đầu")  # no focus: first lines win


def test_where_template_variants(records: dict[str, ProcedureRecord]) -> None:
    base = records["1.004222"]
    agency_only = _render("noi_nop", base.model_copy(update={"cach_thuc": []}))
    assert agency_only is not None and agency_only.sentence.endswith("do Công an Xã thực hiện.")
    channels_only = _render("noi_nop", base.model_copy(update={"co_quan_thuc_hien": None}))
    assert channels_only is not None and "nộp trực tiếp hoặc trực tuyến" in channels_only.sentence
    neither = base.model_copy(update={"co_quan_thuc_hien": None, "cach_thuc": []})
    assert _render("noi_nop", neither) is None


def test_empty_sections_give_no_template(records: dict[str, ProcedureRecord]) -> None:
    base = records["1.004222"]
    assert _render("thoi_han", base.model_copy(update={"cach_thuc": []})) is None
    assert _render("thanh_phan_ho_so", base.model_copy(update={"thanh_phan_ho_so": []})) is None
    assert _render("trinh_tu", base.model_copy(update={"trinh_tu": ["Bước 1:"]})) is None
