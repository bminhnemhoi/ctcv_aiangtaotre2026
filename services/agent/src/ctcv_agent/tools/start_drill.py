"""Tool ``start_drill``: start a scam-vaccine drill in the sandbox (side effect: sandbox).

The output never contains the ``correct`` flag of the options, so a planner cannot leak
the answer to the learner.
"""

from __future__ import annotations

from pydantic import Field

from ctcv_agent.schemas import Identifier, RedFlag, SessionContext, SideEffect, Slug, StrictModel
from ctcv_agent.tools.backends import Backends
from ctcv_core.errors import NotFound

NAME = "start_drill"
SIDE_EFFECT: SideEffect = "sandbox"


class Input(StrictModel):
    """Arguments: the drill scenario key (``drills/scenarios/<key>.json``)."""

    key: Slug


class OptionView(StrictModel):
    """An answer option shown to the learner (no correctness flag)."""

    id: Slug
    text: str


class Output(StrictModel):
    """The started drill as the learner sees it."""

    drill_id: Identifier
    key: Slug
    channel: str
    impersonates: str
    pretext: str
    utterance: str
    options: list[OptionView] = Field(default_factory=list)
    label: str
    red_flags_count: int = Field(ge=0)


def run(inp: Input, ctx: SessionContext, backends: Backends) -> Output:
    """Start the drill ``inp.key`` and return its learner-facing view."""
    started = backends.drills.start(inp.key)
    if started is None:
        raise NotFound(
            "Không tìm thấy bài tập này, bác thử chọn bài khác nhé.", code="DRILL_NOT_FOUND"
        )
    drill_id, spec = started
    flags: list[RedFlag] = spec.red_flags
    return Output(
        drill_id=drill_id,
        key=spec.key,
        channel=spec.channel,
        impersonates=spec.impersonates,
        pretext=spec.pretext,
        utterance=spec.utterance,
        options=[OptionView(id=o.id, text=o.text) for o in spec.options],
        label=spec.label,
        red_flags_count=len(flags),
    )
