"""Tool ``grade_drill``: grade the option chosen in a drill (side effect: sandbox)."""

from __future__ import annotations

from pydantic import Field

from ctcv_agent.schemas import Identifier, RedFlag, SessionContext, SideEffect, Slug, StrictModel
from ctcv_agent.tools.backends import Backends
from ctcv_core.errors import NotFound

NAME = "grade_drill"
SIDE_EFFECT: SideEffect = "sandbox"


class Input(StrictModel):
    """Arguments: the drill and the option the learner picked."""

    drill_id: Identifier
    option_id: Slug


class Output(StrictModel):
    """Score, red flags, debrief and the three things to remember."""

    drill_id: Identifier
    key: Slug
    correct: bool
    score: int = Field(ge=0, le=100)
    red_flags: list[RedFlag] = Field(default_factory=list)
    debrief: str
    three_things: list[str] = Field(min_length=3, max_length=3)


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Grade ``inp.option_id`` for ``inp.drill_id``."""
    grade = backends.drills.grade(inp.drill_id, inp.option_id)
    if grade is None:
        raise NotFound(
            "Cháu không thấy lựa chọn này, bác chọn lại một trong các ô nhé.",
            code="DRILL_ANSWER_NOT_FOUND",
        )
    return Output.model_validate(grade.model_dump())
