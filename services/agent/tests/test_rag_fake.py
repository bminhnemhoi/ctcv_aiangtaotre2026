"""FakeKnowledgeBase: deterministic in-memory KnowledgeBase used by P3/P4/P6 unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctcv_agent.rag.chunker import chunk_record
from ctcv_agent.rag.fake import FakeKnowledgeBase
from ctcv_agent.rag.types import KnowledgeBase, ProcedureRecord

RECORDS_DIR = Path(__file__).parent / "fixtures" / "tthc" / "records"


@pytest.fixture(scope="module")
def records() -> list[ProcedureRecord]:
    return [ProcedureRecord.load(p) for p in sorted(RECORDS_DIR.glob("*.json"))]


@pytest.fixture
def kb(records: list[ProcedureRecord]) -> FakeKnowledgeBase:
    return FakeKnowledgeBase(records)


def test_fake_satisfies_protocol(kb: FakeKnowledgeBase) -> None:
    assert isinstance(kb, KnowledgeBase)
    assert kb.procedure_count() == 3
    assert kb.skill == "dich-vu-cong"


def test_fee_question_finds_permanent_residence(kb: FakeKnowledgeBase) -> None:
    result = kb.search("lệ phí đăng ký thường trú", 5)
    assert result.degraded is False
    assert result.hits[0].chunk.procedure_id == "1.004222"
    assert [h.rank for h in result.hits] == list(range(1, len(result.hits) + 1))
    scores = [h.score for h in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert len(result.hits) <= 5


def test_unaccented_question_still_matches(kb: FakeKnowledgeBase) -> None:
    result = kb.search("le phi dang ky thuong tru", 3)
    assert result.hits[0].chunk.procedure_id == "1.004222"


def test_dialect_question_is_normalised(kb: FakeKnowledgeBase) -> None:
    result = kb.search("Làm căn cước cần chi", 3)
    assert result.hits[0].chunk.procedure_id == "2.000200"


def test_scores_expose_overlap_and_dense_fallback(kb: FakeKnowledgeBase) -> None:
    hit = kb.search("lệ phí đăng ký thường trú", 1).hits[0]
    assert hit.bm25_score == 6.0
    assert hit.dense_score == 1.0
    assert hit.score == 1.0


def test_dense_scores_come_from_mapping(records: list[ProcedureRecord]) -> None:
    kb = FakeKnowledgeBase(records, dense_by_procedure={"1.004222": 0.81})
    hits = kb.search("đăng ký tạm trú thường trú", 10).hits
    by_pid = {h.chunk.procedure_id: h.dense_score for h in hits}
    assert by_pid["1.004222"] == 0.81
    assert 0 < by_pid["1.004194"] <= 1


def test_filter_by_procedure_and_sections(kb: FakeKnowledgeBase) -> None:
    hits = kb.search("hồ sơ", 10, procedure_id="1.004194", sections=["thanh_phan_ho_so"]).hits
    assert hits
    assert {h.chunk.procedure_id for h in hits} == {"1.004194"}
    assert {h.chunk.section for h in hits} == {"thanh_phan_ho_so"}


def test_no_overlap_returns_no_hits(kb: FakeKnowledgeBase) -> None:
    assert kb.search("visa passport", 5).hits == []
    assert kb.search("   ", 5).hits == []


def test_top_k_limits_hits(kb: FakeKnowledgeBase) -> None:
    assert len(kb.search("đăng ký", 2).hits) == 2


def test_lookups(kb: FakeKnowledgeBase, records: list[ProcedureRecord]) -> None:
    record = kb.get_procedure("1.004194")
    assert record is not None and record.ten == "Đăng ký tạm trú"
    assert kb.get_procedure("9.999999") is None
    chunk = kb.get_chunk("tthc-1.004222-phi_le_phi-0")
    assert chunk is not None and "20.000 đồng" in chunk.text
    assert kb.get_chunk("tthc-none") is None


def test_chunks_for_matches_chunker(kb: FakeKnowledgeBase, records: list[ProcedureRecord]) -> None:
    by_id = {r.procedure_id: r for r in records}
    assert kb.chunks_for("1.004222") == chunk_record(by_id["1.004222"], 1200)
    fees = kb.chunks_for("1.004222", sections=["phi_le_phi", "thoi_han"])
    assert [c.section for c in fees] == ["phi_le_phi", "thoi_han"]
    assert kb.chunks_for("9.999999") == []


def test_find_procedures_ranks_best_match_first(kb: FakeKnowledgeBase) -> None:
    found = kb.find_procedures("đăng ký tạm trú", 3)
    assert found[0][0].procedure_id == "1.004194"
    assert len(found) <= 3
    assert len({r.procedure_id for r, _ in found}) == len(found)
    scores = [s for _, s in found]
    assert scores == sorted(scores, reverse=True)
    assert kb.find_procedures("visa passport", 3) == []


def test_find_procedures_respects_limit(kb: FakeKnowledgeBase) -> None:
    assert len(kb.find_procedures("đăng ký", 1)) == 1


def test_custom_chunk_size_and_skill(records: list[ProcedureRecord]) -> None:
    kb = FakeKnowledgeBase(records, max_chars=300, skill="an-toan-so")
    default = FakeKnowledgeBase(records)
    assert len(kb.chunks_for("1.004222")) > len(default.chunks_for("1.004222"))
    assert kb.skill == "an-toan-so"


def test_duplicate_procedure_ids_rejected(records: list[ProcedureRecord]) -> None:
    with pytest.raises(ValueError, match="1.004194"):
        FakeKnowledgeBase([records[0], records[0]])
