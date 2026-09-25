"""Pydantic contracts of the coach agent (brief §7): planner output, tool calls, citations.

Every model forbids unknown fields so that a planner (or an attacker steering it through
pasted text) cannot smuggle extra parameters into a tool call. ``user_id`` never appears
in a tool argument: it travels in :class:`SessionContext`, filled from the JWT by the API
layer (brief D28).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from ctcv_core.config import load_config

# Red-flag codes shared with the drills schema (brief §6, config/schemas/drill.schema.json).
RedFlag = Literal[
    "giuc-chuyen-tien",
    "doi-otp",
    "xung-co-quan",
    "link-la",
    "doa-dam",
    "yeu-cau-cai-app",
    "giu-bi-mat",
    "tai-khoan-la",
]
RED_FLAG_CODES: tuple[str, ...] = get_args(RedFlag)

Role = Literal["citizen", "volunteer", "officer"]
SideEffect = Literal["none", "sandbox", "log"]
SIDE_EFFECTS: frozenset[str] = frozenset(get_args(SideEffect))

_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
_SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"
# Administrative procedure id (ADR-007 C2): the national code ("1.004222") or "bca-<matt>".
PROCEDURE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$"


def _check_skill_group(value: str) -> str:
    """Accept only the skill groups declared in ``config/app.yaml``."""
    allowed = load_config("app")["skill_groups"]
    if value not in allowed:
        raise ValueError(f"nhóm kỹ năng không hợp lệ: {value!r} (cho phép: {', '.join(allowed)})")
    return value


SkillGroup = Annotated[str, AfterValidator(_check_skill_group)]
Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=_ID_PATTERN)]
Slug = Annotated[str, Field(min_length=1, max_length=64, pattern=_SLUG_PATTERN)]
ProcedureId = Annotated[str, Field(min_length=1, max_length=40, pattern=PROCEDURE_ID_PATTERN)]


class StrictModel(BaseModel):
    """Base model: unknown fields are rejected, string whitespace is stripped."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ActionHint(StrictModel):
    """The concrete next action the coach points at: an element, its colour and its label."""

    element_id: Slug
    color: str = Field(min_length=1, max_length=16)
    label: str = Field(min_length=1, max_length=64)


class ToolCall(StrictModel):
    """A tool invocation requested by the planner; arguments are validated by the router."""

    name: Slug
    args: dict[str, Any] = Field(default_factory=dict)


class PlannerOutput(StrictModel):
    """Structured planner reply (config/prompts/coach.v1.md, section "Định dạng đầu ra")."""

    say: str = Field(max_length=600)
    action_hint: ActionHint | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)


class StyleVerdict(StrictModel):
    """Result of :func:`ctcv_agent.guardrails.enforce_style`."""

    ok: bool
    reasons: list[str] = Field(default_factory=list)
    sentences: int = Field(default=0, ge=0)


class Citation(StrictModel):
    """A source backing a factual sentence: official page, title, date and a short quote.

    The optional provenance fields (ADR-007 C4) tell the citizen who published the page and
    when CTCV read it: ``agency``/``source_portal`` name the issuer, ``fetched_at`` is the
    crawl time (UTC), ``section``/``procedure_id`` locate the passage inside a procedure.
    """

    doc_id: Identifier
    url: str = Field(min_length=8, max_length=500, pattern=r"^https?://")
    title: str = Field(min_length=1, max_length=200)
    effective_date: date | None = None
    quote: str = Field(default="", max_length=500)
    agency: str | None = Field(default=None, min_length=1, max_length=200)
    source_portal: str | None = Field(default=None, min_length=1, max_length=200)
    fetched_at: datetime | None = None
    section: str | None = Field(default=None, max_length=32, pattern=r"^[a-z][a-z_]*$")
    procedure_id: ProcedureId | None = None


class SessionContext(StrictModel):
    """Per-turn trusted context built by the API layer from the JWT (brief D28).

    Tools read ``user_id``/``session_id`` from here, never from planner-supplied args.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    user_id: Identifier
    session_id: Identifier | None = None
    role: Role = "citizen"
    class_id: Identifier | None = None


class ToolResult(StrictModel):
    """Outcome of one dispatched tool call, as shown back to the planner."""

    name: Slug
    ok: bool
    output: dict[str, Any] | None = None
    error_code: str | None = None


class TurnResult(StrictModel):
    """What the coach returns for one turn (brief §7, coach.run_turn)."""

    say: str
    action_hint: ActionHint | None = None
    escalate: bool = False
    refused: bool = False
    reasons: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_results: list[ToolResult] = Field(default_factory=list)
