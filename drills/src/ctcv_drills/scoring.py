"""Grade one drill answer and aggregate a before/after vulnerability score.

``score`` is per answer on a 0..100 scale (100 = safe choice made quickly; parameters
in ``rules.yaml: scoring``). ``vulnerability_score`` is the severity-weighted
complement, 0..100, where higher means *more* vulnerable — the number idea §8
expects to drop by ≥ 40 % between the first and the second attempt.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from ctcv_core.errors import ValidationFailed
from ctcv_drills.rules import DrillRules, ScoringRules, load_rules
from ctcv_drills.schema import Drill, RedFlag

MAX_SCORE = 100
OPTION_NOT_FOUND = "OPTION_NOT_FOUND"
OPTION_NOT_FOUND_MESSAGE = "Lựa chọn này không có trong bài luyện, bác chọn lại nhé."


class Grade(BaseModel):
    """Result of one answered drill (what ``POST /v1/drills/{id}/answers`` returns)."""

    model_config = ConfigDict(extra="forbid")

    key: str
    variant: int
    severity: int
    option_id: str
    correct: bool
    seconds: float = Field(ge=0)
    score: int = Field(ge=0, le=MAX_SCORE)
    red_flags: list[RedFlag]
    debrief: str
    three_things: list[str]


def answer_score(correct: bool, seconds: float, scoring: ScoringRules) -> int:
    """Score 0..100: wrong → ``wrong_score``; correct → 100 decaying to ``min_correct_score``."""
    if not correct:
        return scoring.wrong_score
    if seconds <= scoring.fast_seconds:
        return MAX_SCORE
    if seconds >= scoring.slow_seconds:
        return scoring.min_correct_score
    span = scoring.slow_seconds - scoring.fast_seconds
    fraction = (seconds - scoring.fast_seconds) / span
    return round(MAX_SCORE - fraction * (MAX_SCORE - scoring.min_correct_score))


def grade(drill: Drill, option_id: str, seconds: float, rules: DrillRules | None = None) -> Grade:
    """Grade ``option_id`` chosen after ``seconds``; raise ``ValidationFailed`` if unknown."""
    option = drill.option(option_id)
    if option is None:
        raise ValidationFailed(
            OPTION_NOT_FOUND_MESSAGE,
            code=OPTION_NOT_FOUND,
            details={"key": drill.key, "option_id": option_id},
        )
    scoring = (rules or load_rules()).scoring
    elapsed = max(0.0, float(seconds))
    return Grade(
        key=drill.key,
        variant=drill.variant,
        severity=drill.severity,
        option_id=option.id,
        correct=option.correct,
        seconds=elapsed,
        score=answer_score(option.correct, elapsed, scoring),
        red_flags=list(drill.red_flags),
        debrief=drill.debrief,
        three_things=list(drill.three_things),
    )


def vulnerability_score(grades: Sequence[Grade]) -> float:
    """Severity-weighted vulnerability 0..100 (higher = more vulnerable).

    An empty sequence means no evidence of resistance yet and scores 100.0.
    """
    if not grades:
        return float(MAX_SCORE)
    weight = sum(g.severity for g in grades)
    earned = sum(g.severity * g.score for g in grades)
    return round(MAX_SCORE - earned / weight, 1)
