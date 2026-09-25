"""Tool ``get_session_state``: read the structured state of a sandbox session (no side effect)."""

from __future__ import annotations

from ctcv_agent.schemas import Identifier, SessionContext, SideEffect, StrictModel
from ctcv_agent.tools.backends import Backends, SessionSnapshot
from ctcv_core.errors import Forbidden, NotFound

NAME = "get_session_state"
SIDE_EFFECT: SideEffect = "none"


class Input(StrictModel):
    """Arguments: the session to read."""

    session_id: Identifier


class Output(SessionSnapshot):
    """The session snapshot (screen, elements, counters)."""


def ensure_own_session(inp_session_id: str, ctx: SessionContext) -> None:
    """Refuse to read a session other than the one bound to the trusted context."""
    if ctx.session_id is not None and ctx.session_id != inp_session_id:
        raise Forbidden(
            "Bác chỉ xem được bài đang học của mình thôi ạ.",
            code="SESSION_FORBIDDEN",
            details={"tool": NAME},
        )


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Return the snapshot of ``inp.session_id``."""
    ensure_own_session(inp.session_id, ctx)
    snapshot = backends.sessions.get(inp.session_id)
    if snapshot is None:
        raise NotFound(
            "Không tìm thấy phiên học này, bác thử bắt đầu lại bài nhé.", code="SESSION_NOT_FOUND"
        )
    return Output.model_validate(snapshot.model_dump())
