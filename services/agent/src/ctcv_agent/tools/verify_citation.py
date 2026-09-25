"""Tool ``verify_citation``: check that a claim is supported by a guide chunk (no side effect).

The output carries everything the "Nguồn" button shows: the page, its title (clipped to the
:class:`~ctcv_agent.schemas.Citation` limit), the provenance of administrative-procedure
chunks (agency, crawl time, procedure id, section — ADR-007 C4) and a short quote: at most
two sentences of the chunk, the ones sharing most words with the claim, kept in source
order and clipped to 300 characters on a word boundary.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import Field

from ctcv_agent.schemas import Identifier, ProcedureId, SessionContext, SideEffect, StrictModel
from ctcv_agent.tools.backends import Backends
from ctcv_agent.verify import tokenize, verify
from ctcv_core.errors import NotFound

NAME = "verify_citation"
SIDE_EFFECT: SideEffect = "none"
QUOTE_CHARS = 300
QUOTE_SENTENCES = 2
TITLE_CHARS = 200
# A sentence ends at . ! ? … (plus closing quotes/brackets) followed by whitespace, or at a
# line break; dots inside numbers such as 20.000 are never followed by whitespace.
_SENTENCE_END_RE = re.compile(r"(?:(?<=[.!?…])|(?<=[.!?…][\"”’')\]]))\s+|\n+")


class Input(StrictModel):
    """Arguments: the claim the coach wants to say and the document it cites."""

    claim: str = Field(min_length=3, max_length=600)
    doc_id: Identifier


class Output(StrictModel):
    """Support verdict plus the citation fields for the front end's "Nguồn" button."""

    doc_id: Identifier
    supported: bool
    score: float = Field(ge=0.0, le=1.0)
    url: str
    title: str = Field(max_length=TITLE_CHARS)
    effective_date: date | None = None
    quote: str = Field(default="", max_length=QUOTE_CHARS)
    agency: str | None = None
    fetched_at: datetime | None = None
    procedure_id: ProcedureId | None = None
    section: str | None = None


def _clip(text: str, limit: int) -> str:
    """Cut ``text`` to ``limit`` characters on a word boundary, ending with an ellipsis."""
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(" ,;:—-") + "…"


def build_quote(claim: str, text: str) -> str:
    """Pick ≤ 2 sentences of ``text`` sharing most content words with ``claim`` (≤ 300 chars).

    Sentences keep their source order; when none shares a word, the first two are used.
    """
    sentences = [s.strip() for s in _SENTENCE_END_RE.split(text) if s and s.strip()]
    if not sentences:
        return ""
    wanted = tokenize(claim)
    ranked = sorted(range(len(sentences)), key=lambda i: (-len(wanted & tokenize(sentences[i])), i))
    chosen = sorted(ranked[:QUOTE_SENTENCES])
    return _clip(" ".join(sentences[i] for i in chosen), QUOTE_CHARS)


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Score ``inp.claim`` against the chunk ``inp.doc_id``."""
    chunk = backends.guides.get(inp.doc_id)
    if chunk is None:
        raise NotFound(
            "Cháu không tìm thấy nguồn này, để cháu hỏi tình nguyện viên nhé.", code="DOC_NOT_FOUND"
        )
    score, ok = verify(inp.claim, [chunk.text])
    return Output(
        doc_id=chunk.doc_id,
        supported=ok,
        score=score,
        url=chunk.url,
        title=_clip(chunk.title, TITLE_CHARS),
        effective_date=chunk.effective_date,
        quote=build_quote(inp.claim, chunk.text),
        agency=chunk.agency,
        fetched_at=chunk.fetched_at,
        procedure_id=chunk.procedure_id,
        section=chunk.section,
    )
