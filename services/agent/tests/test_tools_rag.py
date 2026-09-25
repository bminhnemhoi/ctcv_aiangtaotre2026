"""Tools read TTHC provenance: GuideChunk/GuideHit metadata and verify_citation quotes (P2b)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ctcv_agent.schemas import Citation, SessionContext
from ctcv_agent.tools import search_guides, verify_citation
from ctcv_agent.tools.backends import (
    SAMPLE_GUIDES,
    Backends,
    GuideChunk,
    InMemoryGuideIndex,
    in_memory_backends,
)
from ctcv_core.text import count_sentences

FETCHED = datetime(2026, 9, 24, 18, 39, 13, tzinfo=UTC)
FEE_TEXT = (
    "Thủ tục Đăng ký thường trú (mã 1.004222) — Phí, lệ phí: Trực tiếp: 20.000 đồng\n"
    "Trực tuyến: 10.000 đồng"
)
LONG_TEXT = (
    "Thủ tục Đăng ký thường trú (mã 1.004222) — Trình tự thực hiện: "
    "Bước 1: Công dân chuẩn bị hồ sơ theo quy định của Luật Cư trú. "
    "Bước 2: Công dân nộp hồ sơ tại Công an cấp xã nơi mình cư trú. "
    "Bước 3: Cán bộ kiểm tra tính pháp lý và nội dung hồ sơ rồi viết phiếu hẹn. "
    "Bước 4: Công dân nộp lệ phí đăng ký thường trú theo quy định hiện hành của nhà nước. "
    "Bước 5: Căn cứ ngày hẹn công dân nhận thông báo kết quả giải quyết thủ tục đăng ký cư trú. "
    "Bước 6: Trường hợp từ chối giải quyết thì cơ quan đăng ký cư trú trả lời bằng văn bản."
)


def _tthc_chunk(doc_id: str, text: str, section: str) -> GuideChunk:
    return GuideChunk(
        doc_id=doc_id,
        url="https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26360",
        title="Đăng ký thường trú — " + ("Phí, lệ phí" if section == "phi_le_phi" else "Trình tự"),
        skill="dich-vu-cong",
        text=text,
        procedure_id="1.004222",
        section=section,
        agency="Bộ Công an",
        fetched_at=FETCHED,
        score=0.032,
    )


@pytest.fixture
def tthc_backends() -> Backends:
    backends = in_memory_backends()
    backends.guides = InMemoryGuideIndex(
        (
            _tthc_chunk("tthc-1.004222-phi_le_phi-0", FEE_TEXT, "phi_le_phi"),
            _tthc_chunk("tthc-1.004222-trinh_tu-0", LONG_TEXT, "trinh_tu"),
        )
    )
    return backends


@pytest.fixture
def ctx() -> SessionContext:
    return SessionContext(user_id="user-demo")


def test_guide_chunk_metadata_is_optional_and_extras_are_forbidden() -> None:
    sample = SAMPLE_GUIDES[0]
    assert (sample.procedure_id, sample.section, sample.agency) == (None, None, None)
    assert sample.fetched_at is None and sample.score is None
    with pytest.raises(ValidationError):
        GuideChunk.model_validate({**sample.model_dump(), "user_id": "x"})


def test_guide_hit_has_the_same_optional_fields() -> None:
    fields = search_guides.GuideHit.model_fields
    for name in ("procedure_id", "section", "agency", "fetched_at", "score"):
        assert name in fields and fields[name].default is None
    with pytest.raises(ValidationError):
        search_guides.GuideHit.model_validate({**SAMPLE_GUIDES[0].model_dump(), "unknown": 1})


def test_search_guides_passes_provenance_through(
    tthc_backends: Backends, ctx: SessionContext
) -> None:
    out = search_guides.run(
        search_guides.Input(query="lệ phí đăng ký thường trú", skill="dich-vu-cong"),
        ctx,
        tthc_backends,
    )
    top = out.results[0]
    assert top.doc_id == "tthc-1.004222-phi_le_phi-0"
    assert (top.procedure_id, top.section, top.agency) == ("1.004222", "phi_le_phi", "Bộ Công an")
    assert top.fetched_at == FETCHED and top.score == pytest.approx(0.032)


def test_search_guides_keeps_legacy_results_without_metadata(
    ctx: SessionContext,
) -> None:
    out = search_guides.run(
        search_guides.Input(query="xác nhận cư trú lệ phí"), ctx, in_memory_backends()
    )
    assert out.results[0].procedure_id is None and out.results[0].agency is None


def test_verify_citation_returns_provenance(tthc_backends: Backends, ctx: SessionContext) -> None:
    out = verify_citation.run(
        verify_citation.Input(
            claim="Lệ phí đăng ký thường trú trực tiếp là 20.000 đồng",
            doc_id="tthc-1.004222-phi_le_phi-0",
        ),
        ctx,
        tthc_backends,
    )
    assert out.supported is True
    assert (out.agency, out.procedure_id, out.section) == ("Bộ Công an", "1.004222", "phi_le_phi")
    assert out.fetched_at == FETCHED
    assert "20.000 đồng" in out.quote


def test_verify_citation_quote_is_at_most_two_sentences_and_300_chars(
    tthc_backends: Backends, ctx: SessionContext
) -> None:
    out = verify_citation.run(
        verify_citation.Input(
            claim="Công dân nộp lệ phí đăng ký thường trú theo quy định",
            doc_id="tthc-1.004222-trinh_tu-0",
        ),
        ctx,
        tthc_backends,
    )
    assert len(out.quote) <= 300
    assert 1 <= count_sentences(out.quote) <= 2
    assert "Bước 4" in out.quote
    assert all(part.strip() in LONG_TEXT for part in out.quote.split("Bước 4"))


def test_quote_prefers_supporting_sentences_in_source_order() -> None:
    quote = verify_citation.build_quote(
        "nộp hồ sơ tại Công an cấp xã và nhận thông báo kết quả", LONG_TEXT
    )
    assert quote.index("Bước 2") < quote.index("Bước 5")
    assert count_sentences(quote) == 2 and len(quote) <= 300


def test_quote_without_overlap_falls_back_to_the_opening() -> None:
    quote = verify_citation.build_quote("zzzz qqqq", LONG_TEXT)
    assert quote.startswith("Thủ tục Đăng ký thường trú") and count_sentences(quote) <= 2


def test_quote_of_a_long_single_sentence_is_clipped_on_a_word() -> None:
    text = "Giấy tờ " + "rất dài " * 80
    quote = verify_citation.build_quote("giấy tờ", text)
    assert len(quote) <= 300 and quote.endswith("…")
    assert verify_citation.build_quote("x", "") == ""


def test_verify_citation_output_always_fits_a_citation(ctx: SessionContext) -> None:
    long_title = "Thủ tục " + "rất dài " * 40
    backends = in_memory_backends()
    backends.guides = InMemoryGuideIndex(
        (
            _tthc_chunk("tthc-x-tong_quan-0", FEE_TEXT, "phi_le_phi").model_copy(
                update={"title": long_title}
            ),
        )
    )
    out = verify_citation.run(
        verify_citation.Input(claim="Lệ phí trực tiếp 20.000 đồng", doc_id="tthc-x-tong_quan-0"),
        ctx,
        backends,
    )
    assert len(out.title) <= 200
    Citation(
        doc_id=out.doc_id,
        url=out.url,
        title=out.title,
        quote=out.quote,
        agency=out.agency,
        fetched_at=out.fetched_at,
        section=out.section,
        procedure_id=out.procedure_id,
    )


def test_read_only_tools_keep_no_side_effect() -> None:
    assert search_guides.SIDE_EFFECT == "none"
    assert verify_citation.SIDE_EFFECT == "none"
    assert "user_id" not in verify_citation.Input.model_fields
