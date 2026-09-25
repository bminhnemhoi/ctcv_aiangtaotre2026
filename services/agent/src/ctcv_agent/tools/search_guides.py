"""Tool ``search_guides``: search the official guide corpus (no side effect).

The guide backend is :class:`~ctcv_agent.tools.backends.GuideIndex`: the in-memory sample
corpus by default, or the administrative-procedure knowledge base once the API calls
``ctcv_agent.rag.index.wire_default_backends`` (ADR-007) — then every hit also carries its
procedure id, section, publishing agency, crawl time and search score.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from ctcv_agent.schemas import (
    Identifier,
    ProcedureId,
    SessionContext,
    SideEffect,
    SkillGroup,
    StrictModel,
)
from ctcv_agent.tools.backends import Backends

NAME = "search_guides"
SIDE_EFFECT: SideEffect = "none"
DEFAULT_TOP_K = 3


class Input(StrictModel):
    """Arguments: a query, an optional skill group and how many chunks to return."""

    query: str = Field(min_length=2, max_length=300)
    skill: SkillGroup | None = None
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=10)


class GuideHit(StrictModel):
    """One matching chunk with the metadata a citation needs (provenance optional)."""

    doc_id: Identifier
    url: str
    title: str
    effective_date: date | None = None
    skill: str
    text: str
    procedure_id: ProcedureId | None = None
    section: str | None = Field(default=None, max_length=32, pattern=r"^[a-z][a-z_]*$")
    agency: str | None = Field(default=None, min_length=1, max_length=200)
    fetched_at: datetime | None = None
    score: float | None = None


class Output(StrictModel):
    """Matching chunks, best first."""

    results: list[GuideHit] = Field(default_factory=list)


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Return up to ``inp.top_k`` chunks for ``inp.query``."""
    chunks = backends.guides.search(inp.query, inp.skill, inp.top_k)
    return Output(results=[GuideHit.model_validate(c.model_dump()) for c in chunks])
