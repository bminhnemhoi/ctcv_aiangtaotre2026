"""Tool ``next_step``: next valid action (element, colour, label) of a session; no side effect."""

from __future__ import annotations

from ctcv_agent.schemas import Identifier, SessionContext, SideEffect, StrictModel
from ctcv_agent.tools.backends import Backends, NextAction
from ctcv_agent.tools.get_session_state import ensure_own_session
from ctcv_core.errors import NotFound

NAME = "next_step"
SIDE_EFFECT: SideEffect = "none"


class Input(StrictModel):
    """Arguments: the session to advise."""

    session_id: Identifier


class Output(NextAction):
    """The next valid action, or ``done`` when the scenario is complete."""


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Return the next valid action of ``inp.session_id``."""
    ensure_own_session(inp.session_id, ctx)
    nxt = backends.sessions.next_action(inp.session_id)
    if nxt is None:
        raise NotFound(
            "Không tìm thấy phiên học này, bác thử bắt đầu lại bài nhé.", code="SESSION_NOT_FOUND"
        )
    return Output.model_validate(nxt.model_dump())
