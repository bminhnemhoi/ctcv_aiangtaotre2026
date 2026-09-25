"""Tool ``log_progress``: append a learning-progress record (side effect: log).

``user_id`` is **not** an argument (brief D28): it comes from the trusted
:class:`SessionContext` the API built from the JWT.
"""

from __future__ import annotations

from pydantic import Field

from ctcv_agent.schemas import SessionContext, SideEffect, SkillGroup, StrictModel
from ctcv_agent.tools.backends import Backends

NAME = "log_progress"
SIDE_EFFECT: SideEffect = "log"


class Input(StrictModel):
    """Arguments: the skill group and level just practised."""

    skill: SkillGroup
    level: int = Field(ge=1, le=3)


class Output(StrictModel):
    """Acknowledgement with the learner's record count (no identifiers echoed)."""

    recorded: bool
    skill: str
    level: int
    total_records: int = Field(ge=0)


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Record ``(ctx.user_id, inp.skill, inp.level)``."""
    total = backends.progress.record(ctx.user_id, inp.skill, inp.level)
    return Output(recorded=True, skill=inp.skill, level=inp.level, total_records=total)
