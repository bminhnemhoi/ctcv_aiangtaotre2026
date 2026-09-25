"""FileKnowledgeBase: load checks, hybrid BM25 + dense search with RRF, filters, degradation."""

from __future__ import annotations

import dataclasses
import json
import random
import shutil
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from ctcv_agent.rag.build import CHUNKS_FILE, META_FILE, VECTORS_FILE, build_index
from ctcv_agent.rag.chunker import chunk_record
from ctcv_agent.rag.embed import EmbedderUnavailable, HashEmbedder, OllamaEmbedder, l2_normalize
from ctcv_agent.rag.index import (
    FileGuideIndex,
    FileKnowledgeBase,
    query_age,
    title_age_range,
    wire_default_backends,
)
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import (
    Chunk,
    KnowledgeBase,
    KnowledgeBaseNotReady,
    ProcedureRecord,
    content_sha256_of,
)
from ctcv_agent.schemas import SessionContext, ToolCall
from ctcv_agent.tools import search_guides, verify_citation
from ctcv_agent.tools.backends import default_backends
from ctcv_agent.tools.router import dispatch
from ctcv_core.config import clear_config_cache

FIXTURE_RECORDS = Path(__file__).parent / "fixtures" / "tthc" / "records"
EMBED_ID = "test/hash-embedder-256"
THUONG_TRU, TAM_TRU, CAN_CUOC = "1.004222", "1.004194", "2.000200"


# ----------------------------------------------------------------------------- fixtures
def _retarget(base: RagSettings, root: Path, model_id: str = EMBED_ID) -> RagSettings:
    kb = dataclasses.replace(base.kb, records_dir=root / "records", index_dir=root / "index")
    embed = dataclasses.replace(base.embed, model_id=model_id)
    return dataclasses.replace(base, kb=kb, embed=embed)


@pytest.fixture
def base_settings(monkeypatch: pytest.MonkeyPatch) -> RagSettings:
    monkeypatch.delenv("CTCV_OLLAMA_BASE_URL", raising=False)
    clear_config_cache()
    return load_rag_settings()


@pytest.fixture
def settings(base_settings: RagSettings, tmp_path: Path) -> RagSettings:
    shutil.copytree(FIXTURE_RECORDS, tmp_path / "records")
    return _retarget(base_settings, tmp_path)


@pytest.fixture
def embedder() -> HashEmbedder:
    return HashEmbedder(dim=256, model_id=EMBED_ID)


@pytest.fixture
def built(settings: RagSettings, embedder: HashEmbedder) -> RagSettings:
    build_index(settings.records_dir, settings.index_dir, embedder, settings)
    return settings


@pytest.fixture
def kb(built: RagSettings, embedder: HashEmbedder) -> FileKnowledgeBase:
    return FileKnowledgeBase.load(built, embedder)


class CountingEmbedder:
    """Wraps an embedder and counts calls."""

    def __init__(self, inner: HashEmbedder) -> None:
        self.inner = inner
        self.model_id = inner.model_id
        self.calls = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return self.inner.embed(texts)


class FailingEmbedder:
    model_id = EMBED_ID
    hosts_contacted = ["localhost:11434"]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbedderUnavailable("ConnectError")


class StaticEmbedder:
    """Returns the same query vector for every text (search timing excludes embedding)."""

    def __init__(self, vector: list[float], model_id: str = EMBED_ID) -> None:
        self.vector = vector
        self.model_id = model_id

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(self.vector) for _ in texts]


# ----------------------------------------------------------------------------- basics
def test_loaded_index_satisfies_protocol(kb: FileKnowledgeBase, embedder: HashEmbedder) -> None:
    assert isinstance(kb, KnowledgeBase)
    assert kb.procedure_count() == 3 and kb.chunk_count() == 24
    assert kb.skill == "dich-vu-cong"
    assert kb.embedder is embedder
    assert kb.meta["embed_model_id"] == EMBED_ID and kb.meta["n_chunks"] == 24
    assert [r.procedure_id for r in kb.procedures()] == [TAM_TRU, THUONG_TRU, CAN_CUOC]
    assert kb.hosts_contacted == []


def test_fee_question_ranks_permanent_residence_first(kb: FileKnowledgeBase) -> None:
    result = kb.search("lệ phí đăng ký thường trú", 5)
    assert result.degraded is False
    assert len(result.hits) == 5
    top = result.hits[0]
    assert top.chunk.procedure_id == THUONG_TRU
    assert top.bm25_score > 0.0 and top.dense_score is not None
    assert [h.rank for h in result.hits] == [1, 2, 3, 4, 5]
    scores = [h.score for h in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert all(h.dense_score is not None for h in result.hits)


COLLOQUIAL = [
    ("le phi dang ky thuong tru", THUONG_TRU),
    ("Làm căn cước cần chi", CAN_CUOC),
    ("làm cccd cho cháu 14 tuổi", CAN_CUOC),
    ("nhập hộ khẩu cho con", THUONG_TRU),
    ("đăng ký ở trọ cần giấy tờ gì", TAM_TRU),
]


@pytest.mark.parametrize(("question", "expected"), COLLOQUIAL)
def test_lexical_channel_handles_accents_dialect_and_synonyms(
    built: RagSettings, question: str, expected: str
) -> None:
    # BM25 only (the hash embedder is a bag of words, not a semantic model): proves that
    # accent folding, dialect rewriting and synonym expansion reach the lexical ranking.
    result = FileKnowledgeBase.load(built, FailingEmbedder()).search(question, 3)
    assert result.hits[0].chunk.procedure_id == expected


@pytest.mark.parametrize(("question", "expected"), COLLOQUIAL[:4])
def test_hybrid_ranking_keeps_the_right_procedure_first(
    kb: FileKnowledgeBase, question: str, expected: str
) -> None:
    assert kb.search(question, 3).hits[0].chunk.procedure_id == expected


class RecordingEmbedder(CountingEmbedder):
    """Counting embedder that also keeps the texts it was asked to embed."""

    def __init__(self, inner: HashEmbedder) -> None:
        super().__init__(inner)
        self.texts: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return super().embed(texts)


def test_dense_channel_embeds_the_normalised_query_with_synonyms(
    built: RagSettings, embedder: HashEmbedder
) -> None:
    recording = RecordingEmbedder(embedder)
    kb = FileKnowledgeBase.load(built, recording)
    kb.search("Làm CCCD  cần chi", 3)
    [text] = recording.texts
    assert text.startswith("làm cccd cần gì")
    assert "căn cước" in text and "thẻ căn cước" in text
    kb.search("lệ phí", 3)
    assert recording.texts[-1] == "lệ phí"


def test_filters_by_procedure_and_sections(kb: FileKnowledgeBase) -> None:
    only_tam_tru = kb.search("giấy tờ cần mang", 10, procedure_id=TAM_TRU)
    assert only_tam_tru.hits and {h.chunk.procedure_id for h in only_tam_tru.hits} == {TAM_TRU}
    fees = kb.search("bao nhiêu tiền", 10, sections=["phi_le_phi"])
    assert fees.hits and {h.chunk.section for h in fees.hits} == {"phi_le_phi"}
    both = kb.search("lệ phí", 10, procedure_id=CAN_CUOC, sections=["phi_le_phi", "thoi_han"])
    assert {(h.chunk.procedure_id, h.chunk.section) for h in both.hits} <= {
        (CAN_CUOC, "phi_le_phi"),
        (CAN_CUOC, "thoi_han"),
    }
    assert kb.search("lệ phí", 5, procedure_id="9.999999").hits == []
    assert kb.search("lệ phí", 5, sections=["khong_co"]).hits == []


def test_blank_query_or_zero_top_k_returns_nothing_without_embedding(
    built: RagSettings, embedder: HashEmbedder
) -> None:
    counting = CountingEmbedder(embedder)
    kb = FileKnowledgeBase.load(built, counting)
    assert kb.search("   ", 5).hits == [] and kb.search("   ", 5).degraded is False
    assert kb.search("lệ phí", 0).hits == []
    assert counting.calls == 0


def test_query_without_lexical_terms_uses_dense_only(kb: FileKnowledgeBase) -> None:
    result = kb.search("và của", 3)
    assert len(result.hits) == 3
    assert all(h.bm25_score == 0.0 and h.dense_score is not None for h in result.hits)


# ----------------------------------------------------------------------------- RRF
def _tiny_kb(settings: RagSettings, rrf_k: int = 60) -> FileKnowledgeBase:
    record = ProcedureRecord.load(FIXTURE_RECORDS / f"{THUONG_TRU}.json")
    template = chunk_record(record, 1200)[0]
    texts = ["lệ phí đăng ký", "đăng ký", "hộ chiếu"]
    chunks = [
        template.model_copy(update={"doc_id": f"tthc-t-{i}", "part": i, "text": text})
        for i, text in enumerate(texts)
    ]
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    retrieval = dataclasses.replace(settings.retrieval, rrf_k=rrf_k)
    tuned = dataclasses.replace(settings, retrieval=retrieval)
    return FileKnowledgeBase(
        [record], chunks, vectors, settings=tuned, embedder=StaticEmbedder([0.6, 0.8, 0.0])
    )


def test_scores_are_reciprocal_rank_fusion(settings: RagSettings) -> None:
    kb = _tiny_kb(settings, rrf_k=60)
    hits = kb.search("lệ phí", 3).hits
    assert [h.chunk.doc_id for h in hits] == ["tthc-t-0", "tthc-t-1", "tthc-t-2"]
    assert hits[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert hits[1].score == pytest.approx(1 / 61)
    assert hits[2].score == pytest.approx(1 / 63)
    assert hits[0].bm25_score > 0.0 and hits[1].bm25_score == hits[2].bm25_score == 0.0
    assert [h.dense_score for h in hits] == pytest.approx([0.6, 0.8, 0.0], abs=1e-6)


def test_rrf_constant_comes_from_settings(settings: RagSettings) -> None:
    hits = _tiny_kb(settings, rrf_k=1).search("lệ phí", 3).hits
    assert hits[0].score == pytest.approx(1 / 2 + 1 / 3)


def test_official_name_is_a_title_field_of_the_bm25_ranking(settings: RagSettings) -> None:
    # Real case: "lệ phí đăng ký thường trú" ranked the fee chunk of "Xóa đăng ký thường trú"
    # first. The official name is scored as a title field of the single BM25 ranking, so the
    # procedure named by the question wins while the score stays a two-list RRF (C4).
    thuong_tru = ProcedureRecord.load(FIXTURE_RECORDS / f"{THUONG_TRU}.json")
    tam_tru = ProcedureRecord.load(FIXTURE_RECORDS / f"{TAM_TRU}.json")
    template = chunk_record(thuong_tru, 1200)[0]
    text = "lệ phí đăng ký lệ phí"
    chunks = [
        template.model_copy(update={"doc_id": "tthc-a-0", "procedure_id": TAM_TRU, "text": text}),
        template.model_copy(
            update={"doc_id": "tthc-b-0", "procedure_id": THUONG_TRU, "text": text}
        ),
    ]
    kb = FileKnowledgeBase(
        [thuong_tru, tam_tru],
        chunks,
        [[1.0, 0.0], [1.0, 0.0]],
        settings=settings,
        embedder=FailingEmbedder(),
    )
    hits = kb.search("lệ phí đăng ký thường trú", 2).hits
    assert [h.chunk.procedure_id for h in hits] == [THUONG_TRU, TAM_TRU]
    assert hits[0].bm25_score > hits[1].bm25_score > 0.0
    k = settings.retrieval.rrf_k
    assert [h.score for h in hits] == pytest.approx([1 / (k + 1), 1 / (k + 2)])


def test_rrf_ties_prefer_the_higher_dense_score(settings: RagSettings) -> None:
    # Real case: "lệ phí đăng ký thường trú" — BM25 #1/dense #2 vs BM25 #2/dense #1 fuse to
    # the same RRF score; the semantic channel must decide, not the chunk order.
    record = ProcedureRecord.load(FIXTURE_RECORDS / f"{THUONG_TRU}.json")
    template = chunk_record(record, 1200)[0]
    texts = ["lệ phí lệ phí", "lệ phí đăng ký thường trú cho công dân", "hộ chiếu"]
    chunks = [
        template.model_copy(update={"doc_id": f"tthc-t-{i}", "part": i, "text": text})
        for i, text in enumerate(texts)
    ]
    vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    kb = FileKnowledgeBase(
        [record], chunks, vectors, settings=settings, embedder=StaticEmbedder([0.6, 0.8, 0.0])
    )
    hits = kb.search("lệ phí", 3).hits
    assert hits[0].score == hits[1].score
    assert hits[0].bm25_score < hits[1].bm25_score
    assert [h.chunk.doc_id for h in hits] == ["tthc-t-1", "tthc-t-0", "tthc-t-2"]


# ----------------------------------------------------------------------------- age constraint
@pytest.mark.parametrize(
    ("question", "age"),
    [
        ("Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?", 14),
        ("lam can cuoc cho chau 14 tuoi can giay to gi", 14),
        ("bà 70 tuổi làm căn cước", 70),
        ("cháu 10 tuổi và cháu 10 tuổi nữa", 10),
        ("căn cước cho người dưới 14 tuổi", None),
        ("người từ đủ 14 tuổi trở lên", None),
        ("cháu 15 tuổi trở lên", None),
        ("cháu 10 tuổi và bà 70 tuổi", None),
        ("lệ phí đăng ký thường trú", None),
    ],
)
def test_query_age_reads_one_exact_age(question: str, age: int | None) -> None:
    assert query_age(question) == age


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Cấp thẻ căn cước cho người dưới 14 tuổi thực hiện tại Công an cấp xã", (0, 14)),
        ("Cấp thẻ Căn cước cho người từ đủ 14 tuổi trở lên thực hiện tại cấp tỉnh", (14, None)),
        ("Cấp giấy cho người đủ 18 tuổi trở lên", (18, None)),
        ("Cấp giấy cho người chưa đủ 16 tuổi", (0, 16)),
        ("Trợ cấp cho người trên 80 tuổi", (81, None)),
        ("Đăng ký thường trú", None),
        ("Xác nhận thông tin về cư trú", None),
    ],
)
def test_title_age_range_is_parsed_from_the_official_name(
    title: str, expected: tuple[int, int | None] | None
) -> None:
    assert title_age_range(title) == expected


def _age_kb(settings: RagSettings) -> FileKnowledgeBase:
    base = ProcedureRecord.load(FIXTURE_RECORDS / f"{CAN_CUOC}.json")
    under = base.model_copy(
        update={
            "procedure_id": "1.014062",
            "ten": "Cấp thẻ căn cước cho người dưới 14 tuổi thực hiện tại Công an cấp xã",
        }
    )
    records = [base, under]
    chunks = [c for r in records for c in chunk_record(r, 1200)]
    embedder = HashEmbedder(dim=128, model_id=EMBED_ID)
    vectors = embedder.embed([c.text for c in chunks])
    return FileKnowledgeBase(records, chunks, vectors, settings=settings, embedder=embedder)


def test_explicit_age_drops_procedures_whose_title_excludes_it(settings: RagSettings) -> None:
    kb = _age_kb(settings)
    fourteen = kb.search("làm căn cước cho cháu 14 tuổi cần giấy tờ gì", 10).hits
    assert fourteen and {h.chunk.procedure_id for h in fourteen} == {CAN_CUOC}
    ten = kb.search("lam can cuoc cho chau 10 tuoi", 10).hits
    assert ten and {h.chunk.procedure_id for h in ten} == {"1.014062"}
    no_age = kb.search("làm căn cước cần giấy tờ gì", 20).hits
    assert {h.chunk.procedure_id for h in no_age} == {CAN_CUOC, "1.014062"}
    assert [r.procedure_id for r, _ in kb.find_procedures("căn cước cho cháu 14 tuổi", 3)] == [
        CAN_CUOC
    ]


def test_age_filter_never_empties_the_result_or_overrides_a_procedure(
    settings: RagSettings,
) -> None:
    kb = _age_kb(settings)
    pinned = kb.search("cháu 14 tuổi", 10, procedure_id="1.014062").hits
    assert pinned and {h.chunk.procedure_id for h in pinned} == {"1.014062"}
    only_under = FileKnowledgeBase(
        [kb.get_procedure("1.014062")],
        kb.chunks_for("1.014062"),
        [kb._rows[i] for i in kb._by_procedure["1.014062"]],
        settings=settings,
        embedder=kb.embedder,
    )
    assert only_under.search("căn cước cho cháu 14 tuổi", 3).hits


def test_constructor_rejects_misaligned_rows(settings: RagSettings) -> None:
    record = ProcedureRecord.load(FIXTURE_RECORDS / f"{THUONG_TRU}.json")
    chunks = chunk_record(record, 1200)[:2]
    embedder = StaticEmbedder([1.0, 0.0])
    with pytest.raises(KnowledgeBaseNotReady) as exc:
        FileKnowledgeBase([record], chunks, [[1.0, 0.0]], settings=settings, embedder=embedder)
    assert exc.value.details == {"reason": "row_count"}
    with pytest.raises(KnowledgeBaseNotReady) as exc:
        FileKnowledgeBase(
            [record], chunks, [[1.0, 0.0], [1.0]], settings=settings, embedder=embedder
        )
    assert exc.value.details == {"reason": "vectors_size"}
    with pytest.raises(KnowledgeBaseNotReady) as exc:
        FileKnowledgeBase(
            [], chunks, [[1.0, 0.0], [0.0, 1.0]], settings=settings, embedder=embedder
        )
    assert exc.value.details == {"reason": "unknown_procedure"}


# ----------------------------------------------------------------------------- degradation
def test_embedder_failure_degrades_to_bm25(built: RagSettings) -> None:
    kb = FileKnowledgeBase.load(built, FailingEmbedder())
    result = kb.search("lệ phí đăng ký thường trú", 5)
    assert result.degraded is True
    assert result.hits and result.hits[0].chunk.procedure_id == THUONG_TRU
    assert all(h.dense_score is None and h.bm25_score > 0.0 for h in result.hits)
    k = built.retrieval.rrf_k
    assert [h.score for h in result.hits] == pytest.approx([1 / (k + r) for r in range(1, 6)])
    assert kb.hosts_contacted == ["localhost:11434"]


def test_wrong_query_dimension_degrades_to_bm25(built: RagSettings) -> None:
    kb = FileKnowledgeBase.load(built, StaticEmbedder([1.0, 0.0]))
    result = kb.search("lệ phí thường trú", 3)
    assert result.degraded is True and result.hits[0].chunk.procedure_id == THUONG_TRU


def test_degraded_query_without_lexical_terms_has_no_hits(built: RagSettings) -> None:
    result = FileKnowledgeBase.load(built, FailingEmbedder()).search("và của", 3)
    assert result.hits == [] and result.degraded is True


# ----------------------------------------------------------------------------- lookups
def test_lookups_follow_chunker_order(kb: FileKnowledgeBase, settings: RagSettings) -> None:
    record = kb.get_procedure(CAN_CUOC)
    assert record is not None and record.ten.startswith("Cấp thẻ Căn cước")
    assert kb.get_procedure("9.999999") is None
    expected = chunk_record(record, settings.retrieval.chunk_max_chars)
    assert kb.chunks_for(CAN_CUOC) == expected
    docs = kb.chunks_for(CAN_CUOC, sections=["thanh_phan_ho_so"])
    assert docs and {c.section for c in docs} == {"thanh_phan_ho_so"}
    assert kb.chunks_for("9.999999") == []
    first = expected[0]
    assert kb.get_chunk(first.doc_id) == first and kb.get_chunk("nope") is None


def test_find_procedures_returns_distinct_best_first(kb: FileKnowledgeBase) -> None:
    found = kb.find_procedures("đăng ký thường trú", 4)
    ids = [record.procedure_id for record, _ in found]
    assert ids[0] == THUONG_TRU and len(ids) == len(set(ids)) <= 3
    scores = [score for _, score in found]
    assert scores == sorted(scores, reverse=True)
    assert len(kb.find_procedures("đăng ký thường trú", 1)) == 1
    assert kb.find_procedures("đăng ký thường trú", 0) == []


def test_find_procedures_ignores_unrelated_queries(kb: FileKnowledgeBase) -> None:
    assert kb.find_procedures("zzzz qqqq", 4) == []


# ----------------------------------------------------------------------------- load checks
def _rewrite(path: Path, transform) -> None:
    path.write_bytes(transform(path.read_bytes()))


def _edit_meta(settings: RagSettings, key: str, value: object) -> None:
    path = settings.index_dir / META_FILE
    meta = json.loads(path.read_text(encoding="utf-8"))
    meta[key] = value
    path.write_text(json.dumps(meta), encoding="utf-8")


def _drop_last_line(data: bytes) -> bytes:
    return b"".join(data.splitlines(keepends=True)[:-1])


def _edit_record(settings: RagSettings) -> None:
    path = settings.records_dir / f"{TAM_TRU}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["ten"] = "Đăng ký tạm trú (bản mới)"
    raw["meta"]["sha256_content"] = content_sha256_of(raw)
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def _retag_chunk(settings: RagSettings) -> None:
    path = settings.index_dir / CHUNKS_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["procedure_id"] = "9.999999"
    lines[0] = json.dumps(first, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


BREAKAGES = {
    "missing_index_dir": (lambda s: shutil.rmtree(s.index_dir), "missing_index"),
    "missing_chunks": (lambda s: (s.index_dir / CHUNKS_FILE).unlink(), "missing_index"),
    "missing_vectors": (lambda s: (s.index_dir / VECTORS_FILE).unlink(), "missing_index"),
    "missing_meta": (lambda s: (s.index_dir / META_FILE).unlink(), "missing_index"),
    "meta_not_json": (lambda s: (s.index_dir / META_FILE).write_text("{"), "bad_meta"),
    "meta_not_object": (lambda s: (s.index_dir / META_FILE).write_text("[]"), "bad_meta"),
    "meta_version": (lambda s: _edit_meta(s, "version", 2), "bad_meta"),
    "meta_dim_type": (lambda s: _edit_meta(s, "dim", "256"), "bad_meta"),
    "chunker_changed": (
        lambda s: _edit_meta(s, "chunker_version", "tthc-chunk/0"),
        "chunker_changed",
    ),
    "row_count": (lambda s: _rewrite(s.index_dir / CHUNKS_FILE, _drop_last_line), "row_count"),
    "vectors_truncated": (
        lambda s: _rewrite(s.index_dir / VECTORS_FILE, lambda b: b[:-4]),
        "vectors_size",
    ),
    "dim_mismatch": (lambda s: _edit_meta(s, "dim", 255), "vectors_size"),
    "vectors_flipped": (
        lambda s: _rewrite(s.index_dir / VECTORS_FILE, lambda b: bytes([b[0] ^ 1]) + b[1:]),
        "vectors_checksum",
    ),
    "chunk_not_json": (
        lambda s: _rewrite(s.index_dir / CHUNKS_FILE, lambda b: b"{\n" + b[b.index(b"\n") + 1 :]),
        "bad_chunks",
    ),
    "chunk_unknown_procedure": (_retag_chunk, "unknown_procedure"),
    "record_changed": (_edit_record, "records_changed"),
    "record_removed": (lambda s: (s.records_dir / f"{TAM_TRU}.json").unlink(), "records_changed"),
    "record_invalid": (
        lambda s: (s.records_dir / f"{TAM_TRU}.json").write_text("{}"),
        "records_invalid",
    ),
    "model_in_meta": (lambda s: _edit_meta(s, "embed_model_id", "other/model"), "model_mismatch"),
}


@pytest.mark.parametrize("name", sorted(BREAKAGES))
def test_broken_or_stale_index_is_not_ready(
    name: str, built: RagSettings, embedder: HashEmbedder
) -> None:
    breakage, reason = BREAKAGES[name]
    breakage(built)
    with pytest.raises(KnowledgeBaseNotReady) as exc:
        FileKnowledgeBase.load(built, embedder)
    assert (exc.value.code, exc.value.status) == ("KB_NOT_READY", 503)
    assert exc.value.details["reason"] == reason


def test_index_of_another_embedding_model_is_not_ready(
    built: RagSettings, base_settings: RagSettings, embedder: HashEmbedder, tmp_path: Path
) -> None:
    configured = _retarget(base_settings, tmp_path, model_id="BAAI/bge-m3")
    with pytest.raises(KnowledgeBaseNotReady) as exc:
        FileKnowledgeBase.load(configured, embedder)
    assert exc.value.details["reason"] == "model_mismatch"


def test_embedder_must_match_configured_model(built: RagSettings) -> None:
    with pytest.raises(KnowledgeBaseNotReady) as exc:
        FileKnowledgeBase.load(built, HashEmbedder(dim=256))
    assert exc.value.details["reason"] == "embedder_mismatch"


def test_default_embedder_is_configured_ollama_without_any_request(
    base_settings: RagSettings, tmp_path: Path
) -> None:
    shutil.copytree(FIXTURE_RECORDS, tmp_path / "records")
    configured = _retarget(base_settings, tmp_path, model_id=base_settings.embed_model_id)
    fake = HashEmbedder(dim=16, model_id=base_settings.embed_model_id)
    build_index(configured.records_dir, configured.index_dir, fake, configured)
    kb = FileKnowledgeBase.load(configured)
    assert isinstance(kb.embedder, OllamaEmbedder)
    assert kb.hosts_contacted == [] and kb.procedure_count() == 3


# ----------------------------------------------------------------------------- performance
def test_search_over_2000_chunks_of_1024_dims_takes_under_a_second(
    settings: RagSettings,
) -> None:
    base = [ProcedureRecord.load(p) for p in sorted(FIXTURE_RECORDS.glob("*.json"))]
    records: list[ProcedureRecord] = []
    chunks: list[Chunk] = []
    while len(chunks) < 2000:
        clone = base[len(records) % 3].model_copy(update={"procedure_id": f"p{len(records):04d}"})
        records.append(clone)
        chunks.extend(chunk_record(clone, settings.retrieval.chunk_max_chars))
    chunks = chunks[:2000]
    rng = random.Random(20260925)
    vectors = [l2_normalize([rng.uniform(-1, 1) for _ in range(1024)]) for _ in chunks]
    query_vector = l2_normalize([rng.uniform(-1, 1) for _ in range(1024)])
    kb = FileKnowledgeBase(
        records, chunks, vectors, settings=settings, embedder=StaticEmbedder(query_vector)
    )
    for question in ("lệ phí đăng ký thường trú", "lam can cuoc cho chau 14 tuoi can giay to gi"):
        started = time.perf_counter()
        result = kb.search(question, 5)
        elapsed = time.perf_counter() - started
        assert len(result.hits) == 5 and result.degraded is False
        assert elapsed < 1.0, f"search mất {elapsed:.3f} s trên 2.000 đoạn × 1.024 chiều"


# ----------------------------------------------------------------------------- tools wiring
def test_guide_index_maps_hits_to_guide_chunks(kb: FileKnowledgeBase) -> None:
    guides = FileGuideIndex(kb)
    found = guides.search("lệ phí đăng ký thường trú", "dich-vu-cong", 3)
    assert len(found) == 3
    top = found[0]
    assert top.procedure_id == THUONG_TRU and top.section is not None
    assert top.agency == "Bộ Công an" and top.fetched_at is not None
    assert top.skill == "dich-vu-cong" and top.url.startswith("https://dichvucong.bocongan")
    assert top.score is not None and top.score > 0.0
    assert guides.search("lệ phí", None, 2) and len(guides.search("lệ phí", None, 2)) == 2
    assert guides.search("lệ phí", "an-toan-so", 3) == []
    same = guides.get(top.doc_id)
    assert same is not None and same.doc_id == top.doc_id and same.score is None
    assert guides.get("nope") is None


def test_wired_backends_serve_the_tools(kb: FileKnowledgeBase) -> None:
    backends = wire_default_backends(kb)
    assert default_backends() is backends
    assert isinstance(backends.guides, FileGuideIndex)
    ctx = SessionContext(user_id="user-demo")
    out = dispatch(
        ToolCall(name="search_guides", args={"query": "lệ phí đăng ký thường trú"}),
        ctx,
        backends,
    )
    assert isinstance(out, search_guides.Output)
    top = out.results[0]
    assert top.procedure_id == THUONG_TRU and top.agency == "Bộ Công an"
    fee_chunk = kb.chunks_for(THUONG_TRU, sections=["phi_le_phi"])[0]
    checked = dispatch(
        ToolCall(
            name="verify_citation",
            args={"claim": "Lệ phí đăng ký thường trú nộp trực tiếp", "doc_id": fee_chunk.doc_id},
        ),
        ctx,
        backends,
    )
    assert isinstance(checked, verify_citation.Output)
    assert checked.procedure_id == THUONG_TRU and checked.section == "phi_le_phi"
    assert checked.agency == "Bộ Công an" and checked.fetched_at == fee_chunk.fetched_at
