"""ADR-007 C3: deterministic chunking of a procedure record into cited passages."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ctcv_agent.rag.chunker import CHUNKER_VERSION, chunk_record
from ctcv_agent.rag.types import SECTION_LABELS, SECTIONS, Chunk, FormRef, ProcedureRecord
from ctcv_core.config import find_repo_root

RECORDS_DIR = Path(__file__).parent / "fixtures" / "tthc" / "records"
DOC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MAX = 1200


def _record(pid: str = "1.004222") -> ProcedureRecord:
    return ProcedureRecord.load(RECORDS_DIR / f"{pid}.json")


def _prefix(record: ProcedureRecord, section: str) -> str:
    code = record.ma_thu_tuc or record.procedure_id
    return f"Thủ tục {record.ten} (mã {code}) — {SECTION_LABELS[section]}: "


def _content(chunk: Chunk, record: ProcedureRecord) -> str:
    prefix = _prefix(record, chunk.section)
    assert chunk.text.startswith(prefix)
    return chunk.text[len(prefix) :]


def _by_section(chunks: list[Chunk], section: str) -> list[Chunk]:
    return [c for c in chunks if c.section == section]


def test_chunker_version() -> None:
    assert CHUNKER_VERSION == "tthc-chunk/1"


@pytest.mark.parametrize("pid", ["1.004222", "2.000200", "1.004194"])
def test_chunking_is_deterministic(pid: str) -> None:
    assert chunk_record(_record(pid), MAX) == chunk_record(_record(pid), MAX)


@pytest.mark.parametrize("pid", ["1.004222", "2.000200", "1.004194"])
def test_doc_ids_follow_contract(pid: str) -> None:
    chunks = chunk_record(_record(pid), MAX)
    ids = [c.doc_id for c in chunks]
    assert len(ids) == len(set(ids))
    for chunk in chunks:
        assert chunk.doc_id == f"tthc-{pid}-{chunk.section}-{chunk.part}"
        assert len(chunk.doc_id) <= 64
        assert DOC_ID_RE.match(chunk.doc_id)


@pytest.mark.parametrize("pid", ["1.004222", "2.000200", "1.004194"])
def test_sections_in_contract_order_with_consecutive_parts(pid: str) -> None:
    chunks = chunk_record(_record(pid), MAX)
    order = [SECTIONS.index(c.section) for c in chunks]
    assert order == sorted(order)
    for section in {c.section for c in chunks}:
        assert [c.part for c in _by_section(chunks, section)] == list(
            range(len(_by_section(chunks, section)))
        )


@pytest.mark.parametrize("pid", ["1.004222", "2.000200", "1.004194"])
def test_title_prefix_and_content_limit(pid: str) -> None:
    record = _record(pid)
    for chunk in chunk_record(record, MAX):
        assert chunk.title == f"{record.ten} — {SECTION_LABELS[chunk.section]}"
        content = _content(chunk, record)
        assert 0 < len(content) <= MAX


def test_metadata_is_copied_from_record() -> None:
    record = _record()
    for chunk in chunk_record(record, MAX):
        assert chunk.procedure_id == record.procedure_id
        assert chunk.url == record.meta.source_url
        assert chunk.agency == record.meta.agency
        assert chunk.source_portal == record.meta.source_portal
        assert chunk.fetched_at == record.meta.fetched_at
        assert chunk.effective_date == record.meta.effective_date
        assert chunk.skill == "dich-vu-cong"
        assert chunk.sha256_content == record.meta.sha256_content


def test_skill_can_be_overridden() -> None:
    chunks = chunk_record(_record(), MAX, skill="an-toan-so")
    assert {c.skill for c in chunks} == {"an-toan-so"}


def test_fee_lines_use_channel_and_fee_text() -> None:
    record = _record()
    (fees,) = _by_section(chunk_record(record, MAX), "phi_le_phi")
    assert _content(fees, record).splitlines() == [
        "Trực tiếp: Trường hợp công dân nộp hồ sơ trực tiếp thu 20.000 đồng/lần đăng ký",
        "Trực tuyến: Trường hợp công dân nộp hồ sơ qua cổng dịch vụ công trực tuyến thu 10.000 "
        "đồng/lần đăng ký.",
    ]


def test_time_limit_lines_use_channel_and_time_limit() -> None:
    record = _record("1.004194")
    (times,) = _by_section(chunk_record(record, MAX), "thoi_han")
    assert _content(times, record).splitlines() == [
        "Trực tiếp: 03 Ngày làm việc",
        "Trực tuyến: 03 Ngày làm việc",
    ]


def test_document_lines_carry_key_case_and_counts() -> None:
    record = _record()
    docs = _by_section(chunk_record(record, MAX), "thanh_phan_ho_so")
    lines = [line for chunk in docs for line in _content(chunk, record).splitlines()]
    first = record.thanh_phan_ho_so[0]
    assert lines[0] == (
        f"[d01] ({first.truong_hop}) {first.ten_giay_to} — bản chính: 0, bản sao: 1"
    )
    assert [line[:5] for line in lines] == [f"[{d.doc_key}]" for d in record.thanh_phan_ho_so]


def test_document_line_without_case_has_no_parentheses() -> None:
    record = _record("2.000200")
    (docs,) = _by_section(chunk_record(record, MAX), "thanh_phan_ho_so")
    first = _content(docs, record).splitlines()[0]
    assert first == (
        "[d01] Phiếu đề nghị giải quyết thủ tục về căn cước (Mẫu DC02 ban hành kèm theo Thông tư "
        "số 17/2024/TT-BCA của Bộ Công an) — bản chính: 1, bản sao: 0"
    )


def test_document_counts_omitted_when_unknown() -> None:
    record = _record("2.000200")
    unknown = record.thanh_phan_ho_so[0].model_copy(update={"ban_chinh": None, "ban_sao": None})
    half = record.thanh_phan_ho_so[1].model_copy(update={"ban_chinh": None})
    record = record.model_copy(update={"thanh_phan_ho_so": [unknown, half]})
    (docs,) = _by_section(chunk_record(record, MAX), "thanh_phan_ho_so")
    lines = _content(docs, record).splitlines()
    assert lines[0].endswith("Bộ Công an)")
    assert lines[1].endswith("— bản sao: 0")


def test_empty_sections_are_skipped() -> None:
    chunks = chunk_record(_record("1.004194"), MAX)
    sections = {c.section for c in chunks}
    assert "phi_le_phi" not in sections  # the page gives no per-channel fee
    assert "bieu_mau" not in sections
    assert {"tong_quan", "trinh_tu", "thanh_phan_ho_so", "thoi_han"} <= sections


def test_overview_names_agency_and_channels() -> None:
    record = _record()
    (overview,) = _by_section(chunk_record(record, MAX), "tong_quan")
    content = _content(overview, record)
    assert "Cơ quan thực hiện: Công an Xã" in content
    assert "Lĩnh vực: Đăng ký, quản lý cư trú" in content
    assert "Trực tiếp: Nộp hồ sơ trực tiếp tại Công an cấp xã." in content
    assert "Kết quả: Cập nhật thông tin" in content


def test_conditions_and_legal_basis() -> None:
    record = _record("2.000200")
    chunks = chunk_record(record, MAX)
    (conditions,) = _by_section(chunks, "dieu_kien")
    assert _content(conditions, record) == "Không"
    legal = "\n".join(_content(c, record) for c in _by_section(chunks, "can_cu_phap_ly"))
    assert "Luật Căn cước (số hiệu 26/2023/QH15)" in legal
    assert "Thông tư 16/2024/TT-BCA quy định về mẫu thẻ căn cước" in legal
    assert "(số hiệu 16/2024/TT-BCA)" not in legal  # number already in the title


def test_forms_section_rendered_when_present() -> None:
    record = _record().model_copy(
        update={
            "bieu_mau": [
                FormRef(ten="Tờ khai thay đổi thông tin cư trú (Mẫu CT01)", url="https://a.vn/x")
            ]
        }
    )
    (forms,) = _by_section(chunk_record(record, MAX), "bieu_mau")
    assert _content(forms, record) == "Tờ khai thay đổi thông tin cư trú (Mẫu CT01)"


def test_long_sections_split_without_losing_text() -> None:
    record = _record()
    small = 300
    chunks = _by_section(chunk_record(record, small), "thanh_phan_ho_so")
    assert len(chunks) > 1
    joined = " ".join(_content(c, record) for c in chunks)
    for doc in record.thanh_phan_ho_so:
        for word in doc.ten_giay_to.split():
            assert word in joined
    assert all(len(_content(c, record)) <= small for c in chunks)


def test_single_long_line_is_split_on_whitespace() -> None:
    record = _record()
    long_step = " ".join(f"tu{i}" for i in range(200))
    record = record.model_copy(update={"trinh_tu": [long_step]})
    chunks = _by_section(chunk_record(record, 100), "trinh_tu")
    words = " ".join(_content(c, record) for c in chunks).split()
    assert words == long_step.split()
    assert all(len(_content(c, record)) <= 100 for c in chunks)


def test_unbreakable_token_is_hard_split() -> None:
    record = _record().model_copy(update={"trinh_tu": ["x" * 250]})
    chunks = _by_section(chunk_record(record, 100), "trinh_tu")
    assert "".join(_content(c, record) for c in chunks) == "x" * 250
    assert [len(_content(c, record)) for c in chunks] == [100, 100, 50]


def test_long_procedure_id_keeps_doc_id_within_64_chars() -> None:
    pid = "bca-" + "9" * 8 + "-" + "a" * 27
    assert len(pid) == 40
    record = _record().model_copy(update={"procedure_id": pid, "ma_thu_tuc": None})
    chunks = chunk_record(record, 200)
    ids = [c.doc_id for c in chunks]
    assert len(ids) == len(set(ids))
    for chunk in chunks:
        assert len(chunk.doc_id) <= 64
        assert DOC_ID_RE.match(chunk.doc_id)
        assert chunk.doc_id.startswith("tthc-bca-")
        assert chunk.doc_id.endswith(f"-{chunk.section}-{chunk.part}")
        assert chunk.text.startswith(f"Thủ tục {record.ten} (mã {pid}) — ")


def test_invalid_max_chars_rejected() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_record(_record(), 0)


def test_long_word_after_short_words_starts_new_piece() -> None:
    record = _record().model_copy(update={"trinh_tu": ["Bước " + "x" * 150]})
    chunks = _by_section(chunk_record(record, 100), "trinh_tu")
    assert [_content(c, record) for c in chunks] == ["Bước", "x" * 100, "x" * 50]


def test_overview_without_channels_or_result() -> None:
    record = _record().model_copy(update={"cach_thuc": [], "ket_qua": None})
    chunks = chunk_record(record, MAX)
    (overview,) = _by_section(chunks, "tong_quan")
    content = _content(overview, record)
    assert "Cách thức thực hiện" not in content
    assert "Kết quả" not in content
    assert not {"phi_le_phi", "thoi_han"} & {c.section for c in chunks}


def test_prompt_examples_quote_real_fixture_chunks() -> None:
    """Every NGUON block in config/prompts/tthc_ask.v1.md is a real chunk (no invented data)."""
    prompt = (find_repo_root() / "config" / "prompts" / "tthc_ask.v1.md").read_text(
        encoding="utf-8"
    )
    blocks = re.findall(r"<<<NGUON id=([^>]+)>>>\n(.*?)\n<<<HET>>>", prompt, re.DOTALL)
    assert len(blocks) >= 2
    chunks = {
        c.doc_id: c
        for pid in ("1.004222", "2.000200", "1.004194")
        for c in chunk_record(_record(pid), MAX)
    }
    for doc_id, text in blocks:
        assert chunks[doc_id].text == text, doc_id
