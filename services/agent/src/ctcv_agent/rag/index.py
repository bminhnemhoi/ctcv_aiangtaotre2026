"""File-backed TTHC knowledge base: hybrid BM25 + dense retrieval fused by RRF (ADR-007 C3/C4).

:meth:`FileKnowledgeBase.load` reads the index written by :mod:`ctcv_agent.rag.build`
(``chunks.jsonl``, ``vectors.f32``, ``index_meta.json``) plus the records, and refuses —
with :class:`~ctcv_agent.rag.types.KnowledgeBaseNotReady` (503) — anything missing, torn,
stale or built with another embedding model. Checks run in this order: files present,
metadata, chunker version, model, chunk rows, vector size and checksum, records set.

:meth:`FileKnowledgeBase.search`:

1. ``q = normalize_query(query)``, then ``expanded = q`` + the
   :func:`~ctcv_agent.rag.query.expand_synonyms` phrases (colloquial → official wording);
2. BM25 over ``expanded``, the procedure's official name scored as a *title field*: the
   lexical score of a chunk is BM25(chunk text) + BM25(name of its procedure) — one
   ranking, so the fusion stays the two-list RRF of the C4 contract. Without the title field
   "lệ phí đăng ký thường trú" put "Xóa đăng ký thường trú" first (its fee chunk repeats the
   words); with it the handwritten eval set gains top-1 hits (test split 96 → 102 of 115);
3. dense cosine: ``embed(expanded)`` · every candidate row (pure Python over ``array('f')``,
   the rows are unit vectors) — when the embedder fails the result is ``degraded``, BM25
   only. Embedding the expanded text (not bare ``q``) lifts the right procedure for
   colloquial or unaccented questions (bge-m3 on the fixtures: "làm cccd…" 0.52 → 0.72,
   "lam can cuoc…" 0.48 → 0.72, "ở trọ"/"hộ khẩu" now rank tạm trú/thường trú first);
4. procedure/section filters restrict the candidates before scoring; without a
   ``procedure_id``, a question stating one exact age ("cháu 14 tuổi") also drops the
   procedures whose official name excludes that age ("… dưới 14 tuổi" vs "… từ đủ 14 tuổi
   trở lên", bounds parsed from the name, see :func:`title_age_range`) — neither channel
   can reason about age ranges (bge-m3 ranks "dưới 14 tuổi" first even for "con 16
   tuổi") — unless that would leave no candidate;
5. reciprocal rank fusion ``Σ 1 / (rrf_k + rank)`` over the BM25 ranking (chunks with a
   positive score) and the dense ranking; equal fused scores are ordered by dense score,
   then BM25 score, then chunker order.

:class:`FileGuideIndex` adapts any :class:`~ctcv_agent.rag.types.KnowledgeBase` to the
``GuideIndex`` protocol read by the ``search_guides``/``verify_citation`` tools, and
:func:`wire_default_backends` installs it as the process-wide guide backend.
"""

from __future__ import annotations

import hashlib
import json
import logging
import operator
import re
from array import array
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from ctcv_agent.rag.bm25 import BM25Index, tokenize_for_bm25
from ctcv_agent.rag.build import (
    CHUNKS_FILE,
    INDEX_VERSION,
    META_FILE,
    VECTORS_FILE,
    IndexBuildError,
    load_records,
    records_digest,
    vectors_from_bytes,
)
from ctcv_agent.rag.chunker import CHUNKER_VERSION
from ctcv_agent.rag.embed import Embedder, EmbedderUnavailable, OllamaEmbedder
from ctcv_agent.rag.query import expand_synonyms, fold_accents, normalize_query
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import (
    Chunk,
    Hit,
    KnowledgeBase,
    KnowledgeBaseNotReady,
    ProcedureRecord,
    SearchResult,
)
from ctcv_agent.tools.backends import (
    Backends,
    GuideChunk,
    InMemoryDrillStore,
    InMemoryEscalationSink,
    InMemoryProgressSink,
    InMemorySessionStore,
    set_default_backends,
)

_LOG = logging.getLogger(__name__)
_FLOAT32_BYTES = 4
# Age expressions, matched on accent-free lower-case text ("tuổi" → "tuoi").
_AGE_RE = re.compile(r"(?<!\w)(\d{1,3})\s*tuoi(?!\w)")
_RANGE_WORDS_BEFORE = frozenset(
    {"duoi", "tren", "du", "tu", "chua", "hon", "qua", "den", "khoang", "toi"}
)
_RANGE_AFTER_RE = re.compile(r"\s*(?:tro len|tro xuong|tro di|tro lai)(?!\w)")
_TITLE_BELOW_RE = re.compile(r"(?<!\w)(?:duoi|chua du)\s+(\d{1,3})\s*tuoi(?!\w)")
_TITLE_FROM_RE = re.compile(r"(?<!\w)(?:tu du|du|tu)\s+(\d{1,3})\s*tuoi\s+tro len(?!\w)")
_TITLE_ABOVE_RE = re.compile(r"(?<!\w)tren\s+(\d{1,3})\s*tuoi(?!\w)")
AgeRange = tuple[int, int | None]


# ----------------------------------------------------------------------------- age constraint
def query_age(text: str) -> int | None:
    """The one exact age a question states ("cháu 14 tuổi" → 14), else None.

    Ages written as a range ("dưới 14 tuổi", "15 tuổi trở lên", "từ 6 đến 14 tuổi") or
    several different ages give None, so the caller does not filter.
    """
    folded = fold_accents(text.casefold())
    ages: set[int] = set()
    for match in _AGE_RE.finditer(folded):
        before = folded[: match.start()].split()[-1:]
        if before and before[0] in _RANGE_WORDS_BEFORE:
            return None
        if _RANGE_AFTER_RE.match(folded, match.end()):
            return None
        ages.add(int(match.group(1)))
    return ages.pop() if len(ages) == 1 else None


def title_age_range(title: str) -> AgeRange | None:
    """Age bounds ``(min_inclusive, max_exclusive|None)`` written in a procedure name."""
    folded = fold_accents(title.casefold())
    if below := _TITLE_BELOW_RE.search(folded):
        return 0, int(below.group(1))
    if start := _TITLE_FROM_RE.search(folded):
        return int(start.group(1)), None
    if above := _TITLE_ABOVE_RE.search(folded):
        return int(above.group(1)) + 1, None
    return None


def _age_allowed(bounds: AgeRange | None, age: int) -> bool:
    """True when ``age`` fits ``bounds`` (no bounds → always)."""
    if bounds is None:
        return True
    low, high = bounds
    return age >= low and (high is None or age < high)


# ----------------------------------------------------------------------------- loading
def _read_meta(index_dir: Path, settings: RagSettings) -> dict[str, Any]:
    """Read and check ``index_meta.json`` against the code and the configured model."""
    try:
        meta = json.loads((index_dir / META_FILE).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise KnowledgeBaseNotReady("bad_meta") from exc
    dims_ok = isinstance(meta, dict) and all(
        isinstance(meta.get(key), int) and not isinstance(meta.get(key), bool)
        for key in ("dim", "n_chunks")
    )
    if not dims_ok or meta.get("version") != INDEX_VERSION or meta["dim"] < 1:
        raise KnowledgeBaseNotReady("bad_meta")
    if meta.get("chunker_version") != CHUNKER_VERSION:
        raise KnowledgeBaseNotReady("chunker_changed")
    if meta.get("embed_model_id") != settings.embed_model_id:
        raise KnowledgeBaseNotReady("model_mismatch")
    return meta


def _read_chunks(path: Path, expected: int) -> list[Chunk]:
    """Parse ``chunks.jsonl`` (one chunk per non-empty line) and check the row count."""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        chunks = [Chunk.model_validate_json(line) for line in lines]
    except ValidationError as exc:
        raise KnowledgeBaseNotReady("bad_chunks") from exc
    if len(chunks) != expected:
        raise KnowledgeBaseNotReady("row_count")
    return chunks


def _read_rows(path: Path, meta: Mapping[str, Any]) -> list[array]:
    """Read ``vectors.f32``, check size and checksum, and split it into rows."""
    blob = path.read_bytes()
    dim, count = int(meta["dim"]), int(meta["n_chunks"])
    if len(blob) != dim * count * _FLOAT32_BYTES:
        raise KnowledgeBaseNotReady("vectors_size")
    if hashlib.sha256(blob).hexdigest() != meta.get("vectors_sha256"):
        raise KnowledgeBaseNotReady("vectors_checksum")
    flat = vectors_from_bytes(blob)
    return [flat[i * dim : (i + 1) * dim] for i in range(count)]


def _read_records(records_dir: Path, meta: Mapping[str, Any]) -> list[ProcedureRecord]:
    """Load the records and check they are exactly the set the index was built from."""
    try:
        records = load_records(records_dir)
    except IndexBuildError as exc:
        raise KnowledgeBaseNotReady("records_invalid") from exc
    if records_digest(records) != meta.get("records_sha256"):
        raise KnowledgeBaseNotReady("records_changed")
    return records


# ----------------------------------------------------------------------------- knowledge base
class FileKnowledgeBase:
    """Read-only :class:`~ctcv_agent.rag.types.KnowledgeBase` over an in-memory index.

    Args:
        records: Procedure records; every chunk must belong to one of them.
        chunks: Chunks in index order.
        vectors: One L2-normalised row per chunk, all of the same dimension.
        settings: Resolved RAG settings (retrieval parameters, gate floor, skill).
        embedder: Embeds queries; its failure degrades search to BM25.
        meta: ``index_meta.json`` content, exposed read-only as :attr:`meta`.

    Raises:
        KnowledgeBaseNotReady: rows and chunks do not line up, or a chunk has no record.
    """

    def __init__(
        self,
        records: Iterable[ProcedureRecord],
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        *,
        settings: RagSettings,
        embedder: Embedder,
        meta: Mapping[str, Any] | None = None,
    ) -> None:
        """Index records, chunks and rows; build the BM25 postings."""
        self._settings = settings
        self._embedder = embedder
        self._meta = MappingProxyType(dict(meta or {}))
        self._records = {r.procedure_id: r for r in records}
        self._age_bounds = {pid: title_age_range(r.ten) for pid, r in self._records.items()}
        self._chunks = list(chunks)
        self._rows = [row if isinstance(row, array) else array("f", row) for row in vectors]
        self._check_alignment()
        self._by_id = {c.doc_id: i for i, c in enumerate(self._chunks)}
        self._by_procedure: dict[str, list[int]] = {}
        for i, chunk in enumerate(self._chunks):
            self._by_procedure.setdefault(chunk.procedure_id, []).append(i)
        fold, k1, b = (
            settings.retrieval.accent_fold,
            settings.retrieval.bm25_k1,
            settings.retrieval.bm25_b,
        )
        self._bm25 = BM25Index((tokenize_for_bm25(c.text, fold) for c in self._chunks), k1, b)
        self._pids = sorted(self._records)
        names = (tokenize_for_bm25(self._records[pid].ten, fold) for pid in self._pids)
        self._name_bm25 = BM25Index(names, k1, b)

    def _check_alignment(self) -> None:
        if len(self._rows) != len(self._chunks):
            raise KnowledgeBaseNotReady("row_count")
        dims = {len(row) for row in self._rows}
        if len(dims) > 1 or 0 in dims:
            raise KnowledgeBaseNotReady("vectors_size")
        self._dim = dims.pop() if dims else 0
        if any(c.procedure_id not in self._records for c in self._chunks):
            raise KnowledgeBaseNotReady("unknown_procedure")

    @classmethod
    def load(
        cls, settings: RagSettings | None = None, embedder: Embedder | None = None
    ) -> FileKnowledgeBase:
        """Load ``kb.index_dir`` and ``kb.records_dir`` (checks: module docstring).

        Args:
            settings: Resolved settings; loaded from ``config/rag.yaml`` when omitted.
            embedder: Query embedder; defaults to :class:`OllamaEmbedder` (no request is
                made while loading).

        Raises:
            KnowledgeBaseNotReady: missing, torn or stale index, or model mismatch.
        """
        s = settings or load_rag_settings()
        index_dir = s.index_dir
        if not all((index_dir / name).is_file() for name in (META_FILE, CHUNKS_FILE, VECTORS_FILE)):
            raise KnowledgeBaseNotReady("missing_index")
        meta = _read_meta(index_dir, s)
        chunks = _read_chunks(index_dir / CHUNKS_FILE, int(meta["n_chunks"]))
        rows = _read_rows(index_dir / VECTORS_FILE, meta)
        records = _read_records(s.records_dir, meta)
        active = embedder or OllamaEmbedder(s)
        if active.model_id != s.embed_model_id:
            raise KnowledgeBaseNotReady("embedder_mismatch")
        return cls(records, chunks, rows, settings=s, embedder=active, meta=meta)

    # ------------------------------------------------------------------------- properties
    @property
    def skill(self) -> str:
        """Skill group of every chunk (``config/rag.yaml: kb.skill``)."""
        return self._settings.kb.skill

    @property
    def meta(self) -> Mapping[str, Any]:
        """Read-only ``index_meta.json`` content (empty when built in memory)."""
        return self._meta

    @property
    def embedder(self) -> Embedder:
        """The query embedder."""
        return self._embedder

    @property
    def hosts_contacted(self) -> list[str]:
        """``host:port`` values the embedder has contacted so far (empty for test doubles)."""
        return list(getattr(self._embedder, "hosts_contacted", ()))

    # ------------------------------------------------------------------------- search
    def _candidates(self, procedure_id: str | None, sections: Sequence[str] | None) -> list[int]:
        indices = (
            self._by_procedure.get(procedure_id, [])
            if procedure_id is not None
            else range(len(self._chunks))
        )
        if sections is None:
            return list(indices)
        wanted = set(sections)
        return [i for i in indices if self._chunks[i].section in wanted]

    def _age_filtered(self, q: str, candidates: list[int]) -> list[int]:
        """Drop candidates whose procedure name excludes the question's exact age."""
        age = query_age(q)
        if age is None:
            return candidates
        bounds = self._age_bounds
        kept = [i for i in candidates if _age_allowed(bounds[self._chunks[i].procedure_id], age)]
        return kept or candidates

    def _lexical(self, terms: Sequence[str], candidates: Sequence[int]) -> dict[int, float]:
        """Positive lexical scores: BM25 of the chunk text + BM25 of its procedure's name."""
        if not terms:
            return {}
        scores = self._bm25.scores(terms)
        names = dict(zip(self._pids, self._name_bm25.scores(terms), strict=True))
        combined = ((i, scores[i] + names[self._chunks[i].procedure_id]) for i in candidates)
        return {i: score for i, score in combined if score > 0.0}

    def _dense(self, expanded: str, candidates: Sequence[int]) -> dict[int, float] | None:
        """Cosine of every candidate with ``embed(expanded)``; None when the embedder fails."""
        try:
            vectors = self._embedder.embed([expanded])
        except EmbedderUnavailable as exc:
            _LOG.warning("dense retrieval unavailable: %s", (exc.details or {}).get("reason"))
            return None
        if len(vectors) != 1 or len(vectors[0]) != self._dim:
            _LOG.warning("dense retrieval unavailable: query vector dimension mismatch")
            return None
        query = array("f", vectors[0])
        mul = operator.mul
        return {i: sum(map(mul, query, self._rows[i])) for i in candidates}

    def _fuse(
        self, lexical: Mapping[int, float], dense: Mapping[int, float] | None
    ) -> list[tuple[float, int]]:
        """Reciprocal rank fusion, best first; ties by dense, then BM25, then chunker order."""
        k = self._settings.retrieval.rrf_k
        semantic = dense or {}
        fused: dict[int, float] = {}
        for ranking in (lexical, semantic):
            ordered = sorted(ranking, key=lambda i, r=ranking: (-r[i], i))
            for rank, index in enumerate(ordered, start=1):
                fused[index] = fused.get(index, 0.0) + 1.0 / (k + rank)
        return sorted(
            ((score, i) for i, score in fused.items()),
            key=lambda x: (-x[0], -semantic.get(x[1], 0.0), -lexical.get(x[1], 0.0), x[1]),
        )

    def search(
        self,
        query: str,
        top_k: int,
        *,
        procedure_id: str | None = None,
        sections: Sequence[str] | None = None,
    ) -> SearchResult:
        """Hybrid search (see module docstring); ``degraded`` when dense retrieval failed."""
        q = normalize_query(query, self._settings)
        candidates = self._candidates(procedure_id, sections)
        if procedure_id is None:
            candidates = self._age_filtered(q, candidates)
        if top_k < 1 or not q or not candidates:
            return SearchResult()
        expanded = " ".join([q, *expand_synonyms(q, self._settings)])
        terms = tokenize_for_bm25(expanded, self._settings.retrieval.accent_fold)
        lexical = self._lexical(terms, candidates)
        dense = self._dense(expanded, candidates)
        hits = [
            Hit(
                chunk=self._chunks[i],
                score=score,
                bm25_score=lexical.get(i, 0.0),
                dense_score=None if dense is None else dense[i],
                rank=rank,
            )
            for rank, (score, i) in enumerate(self._fuse(lexical, dense)[:top_k], start=1)
        ]
        return SearchResult(hits=hits, degraded=dense is None)

    # ------------------------------------------------------------------------- lookups
    def get_procedure(self, pid: str) -> ProcedureRecord | None:
        """Return the record with this ``procedure_id`` or None."""
        return self._records.get(pid)

    def get_chunk(self, doc_id: str) -> Chunk | None:
        """Return the chunk with this ``doc_id`` or None."""
        index = self._by_id.get(doc_id)
        return None if index is None else self._chunks[index]

    def chunks_for(self, pid: str, sections: Sequence[str] | None = None) -> list[Chunk]:
        """Return a procedure's chunks in chunker order, optionally filtered by section."""
        return [self._chunks[i] for i in self._candidates(pid, sections)]

    def find_procedures(self, query: str, limit: int) -> list[tuple[ProcedureRecord, float]]:
        """Distinct procedures ranked by their best hit, with that hit's fused (RRF) score.

        A hit counts only when it matches lexically (BM25 > 0) or its dense score reaches
        ``gate.min_dense_score``, so an unrelated query finds nothing.
        """
        if limit < 1:
            return []
        floor = self._settings.gate.min_dense_score
        best: dict[str, float] = {}
        for hit in self.search(query, len(self._chunks)).hits:
            pid = hit.chunk.procedure_id
            relevant = hit.bm25_score > 0.0 or (hit.dense_score or 0.0) >= floor
            if relevant and pid not in best:
                best[pid] = hit.score
            if len(best) == limit:
                break
        return [(self._records[pid], score) for pid, score in best.items()]

    def procedure_count(self) -> int:
        """Return how many procedure records are loaded."""
        return len(self._records)

    def chunk_count(self) -> int:
        """Return how many chunks are indexed."""
        return len(self._chunks)

    def procedures(self) -> list[ProcedureRecord]:
        """All records sorted by ``procedure_id``."""
        return [self._records[pid] for pid in sorted(self._records)]


# ----------------------------------------------------------------------------- tools adapter
def _guide_chunk(chunk: Chunk, score: float | None = None) -> GuideChunk:
    """Map a TTHC chunk to the tools' :class:`GuideChunk` (citation metadata included)."""
    return GuideChunk(
        doc_id=chunk.doc_id,
        url=chunk.url,
        title=chunk.title,
        effective_date=chunk.effective_date,
        skill=chunk.skill,
        text=chunk.text,
        procedure_id=chunk.procedure_id,
        section=chunk.section,
        agency=chunk.agency,
        fetched_at=chunk.fetched_at,
        score=score,
    )


class FileGuideIndex:
    """``GuideIndex`` (tools) over a :class:`~ctcv_agent.rag.types.KnowledgeBase`.

    Args:
        kb: The knowledge base; its ``skill`` attribute (when present) short-cuts searches
            for another skill group without embedding the query.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        """Wrap ``kb``."""
        self._kb = kb
        self.skill: str | None = getattr(kb, "skill", None)

    def search(self, query: str, skill: str | None, top_k: int) -> list[GuideChunk]:
        """Up to ``top_k`` chunks for ``query``; another ``skill`` group yields ``[]``."""
        if skill is not None and self.skill is not None and skill != self.skill:
            return []
        hits = self._kb.search(query, top_k).hits
        return [_guide_chunk(h.chunk, h.score) for h in hits if skill in (None, h.chunk.skill)]

    def get(self, doc_id: str) -> GuideChunk | None:
        """Return the chunk ``doc_id`` as a :class:`GuideChunk` or None."""
        chunk = self._kb.get_chunk(doc_id)
        return None if chunk is None else _guide_chunk(chunk)


def wire_default_backends(kb: KnowledgeBase) -> Backends:
    """Install ``FileGuideIndex(kb)`` as the process-wide guide backend and return it all."""
    backends = Backends(
        sessions=InMemorySessionStore(),
        guides=FileGuideIndex(kb),
        drills=InMemoryDrillStore(),
        progress=InMemoryProgressSink(),
        escalations=InMemoryEscalationSink(),
    )
    set_default_backends(backends)
    return backends
