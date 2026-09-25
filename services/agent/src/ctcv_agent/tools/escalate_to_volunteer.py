"""Tool ``escalate_to_volunteer``: flag the session for a human (side effect: log).

The reason is redacted before it is stored so a planner cannot smuggle PII into the
volunteer dashboard.
"""

from __future__ import annotations

from pydantic import Field

from ctcv_agent.guardrails import redact_pii
from ctcv_agent.schemas import Identifier, SessionContext, SideEffect, StrictModel
from ctcv_agent.tools.backends import Backends

NAME = "escalate_to_volunteer"
SIDE_EFFECT: SideEffect = "log"
REASON_MAX = 200


class Input(StrictModel):
    """Arguments: a short reason (no PII)."""

    reason: str = Field(min_length=1, max_length=REASON_MAX)


class Output(StrictModel):
    """The created ticket."""

    escalated: bool
    ticket_id: Identifier


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Create an escalation ticket for ``ctx``."""
    ticket_id = backends.escalations.flag(ctx.user_id, ctx.session_id, redact_pii(inp.reason))
    return Output(escalated=True, ticket_id=ticket_id)
