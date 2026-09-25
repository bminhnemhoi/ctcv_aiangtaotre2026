"""In-memory :class:`~ctcv_agent.rag.types.KnowledgeBase` for unit tests (no model, no disk).

Scoring is deliberately simple and deterministic: a chunk scores the number of distinct
query content tokens it contains, a token also matching through its accent-free form
(``"le phi"`` finds ``"lệ phí"``). ``dense_score`` is taken from ``dense_by_procedure`` so a
test can drive the answer gate, otherwise it is the share of query tokens found. Ties keep
chunker order. The real index is ``ctcv_agent.rag.index.FileKnowledgeBase``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from ctcv_agent.rag.chunker import chunk_record
from ctcv_agent.rag.query import content_tokens, fold_accents, normalize_query
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import Chunk, Hit, ProcedureRecord, SearchResult


def _token_set(text: str) -> frozenset[str]:
    """Content tokens of ``text`` plus their accent-free forms."""
    tokens = content_tokens(text)
    return frozenset(tokens) | frozenset(fold_accents(t) for t in tokens)


class FakeKnowledgeBase:
    """Deterministic ``KnowledgeBase`` over a handful of :class:`ProcedureRecord`.

    Args:
        records: Procedure records; duplicate ``procedure_id`` values are rejected.
        dense_by_procedure: Optional fixed dense score per procedure id.
        max_chars: Chunk size; defaults to ``retrieval.chunk_max_chars``.
        skill: Skill label of the chunks; defaults to ``kb.skill``.
        settings: Settings used for defaults and query normalisation.
    """

    def __init__(
        self,
        records: Iterable[ProcedureRecord],
        dense_by_procedure: Mapping[str, float] | None = None,
        *,
        max_chars: int | None = None,
        skill: str | None = None,
        settings: RagSettings | None = None,
    ) -> None:
        """Chunk every record and index its tokens."""
        self._settings = settings or load_rag_settings()
        self._dense = dict(dense_by_procedure or {})
        self.skill = skill or self._settings.kb.skill
        size = max_chars or self._settings.retrieval.chunk_max_chars
        self._records: dict[str, ProcedureRecord] = {}
        self._chunks: list[Chunk] = []
        for record in records:
            if record.procedure_id in self._records:
                raise ValueError(f"procedure_id trùng: {record.procedure_id}")
            self._records[record.procedure_id] = record
            self._chunks.extend(chunk_record(record, size, skill=self.skill))
        self._by_id = {chunk.doc_id: chunk for chunk in self._chunks}
        self._tokens = [_token_set(chunk.text) for chunk in self._chunks]

    def _query_tokens(self, query: str) -> list[str]:
        """Distinct content tokens of the normalised query, in order."""
        return list(dict.fromkeys(content_tokens(normalize_query(query, self._settings))))

    def _overlap(self, query_tokens: list[str], index: int) -> int:
        chunk_tokens = self._tokens[index]
        return sum(1 for t in query_tokens if t in chunk_tokens or fold_accents(t) in chunk_tokens)

    def _allowed(self, chunk: Chunk, pid: str | None, sections: Sequence[str] | None) -> bool:
        if pid is not None and chunk.procedure_id != pid:
            return False
        return sections is None or chunk.section in sections

    def search(
        self,
        query: str,
        top_k: int,
        *,
        procedure_id: str | None = None,
        sections: Sequence[str] | None = None,
    ) -> SearchResult:
        """Rank chunks by token overlap with ``query`` (see module docstring)."""
        tokens = self._query_tokens(query)
        if not tokens:
            return SearchResult()
        scored = [
            (self._overlap(tokens, i), i)
            for i, chunk in enumerate(self._chunks)
            if self._allowed(chunk, procedure_id, sections)
        ]
        ranked = sorted((item for item in scored if item[0] > 0), key=lambda x: (-x[0], x[1]))
        hits = []
        for rank, (overlap, index) in enumerate(ranked[:top_k], start=1):
            chunk = self._chunks[index]
            ratio = round(overlap / len(tokens), 4)
            dense = self._dense.get(chunk.procedure_id, ratio)
            hits.append(
                Hit(
                    chunk=chunk,
                    score=ratio,
                    bm25_score=float(overlap),
                    dense_score=dense,
                    rank=rank,
                )
            )
        return SearchResult(hits=hits, degraded=False)

    def get_procedure(self, pid: str) -> ProcedureRecord | None:
        """Return the record with this id or None."""
        return self._records.get(pid)

    def get_chunk(self, doc_id: str) -> Chunk | None:
        """Return the chunk with this ``doc_id`` or None."""
        return self._by_id.get(doc_id)

    def chunks_for(self, pid: str, sections: Sequence[str] | None = None) -> list[Chunk]:
        """Return the procedure's chunks in chunker order, optionally filtered by section."""
        return [c for c in self._chunks if self._allowed(c, pid, sections)]

    def find_procedures(self, query: str, limit: int) -> list[tuple[ProcedureRecord, float]]:
        """Best-scoring distinct procedures (score = dense score of their best hit)."""
        best: dict[str, float] = {}
        for hit in self.search(query, len(self._chunks)).hits:
            pid = hit.chunk.procedure_id
            if pid not in best:
                best[pid] = hit.dense_score if hit.dense_score is not None else hit.score
        ordered = sorted(best.items(), key=lambda item: -item[1])[:limit]
        return [(self._records[pid], score) for pid, score in ordered]

    def procedure_count(self) -> int:
        """Return the number of loaded records."""
        return len(self._records)
