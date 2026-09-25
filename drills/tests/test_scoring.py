from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctcv_core.errors import ValidationFailed
from ctcv_drills.rules import ScoringRules, load_rules
from ctcv_drills.schema import Drill
from ctcv_drills.scoring import (
    MAX_SCORE,
    OPTION_NOT_FOUND,
    Grade,
    answer_score,
    grade,
    vulnerability_score,
)


def make_grade(**overrides: object) -> Grade:
    base = {
        "key": "a",
        "variant": 1,
        "severity": 1,
        "option_id": "x",
        "correct": True,
        "seconds": 1,
        "score": 100,
        "red_flags": [],
        "debrief": "d",
        "three_things": ["1", "2", "3"],
    }
    return Grade.model_validate({**base, **overrides})


@pytest.fixture(scope="module")
def scoring() -> ScoringRules:
    return load_rules().scoring


def test_correct_fast_is_full_score(sample: Drill, scoring: ScoringRules) -> None:
    result = grade(sample, "cup-may", scoring.fast_seconds)
    assert isinstance(result, Grade)
    assert result.score == MAX_SCORE and result.correct
    assert result.red_flags == list(sample.red_flags)
    assert result.debrief == sample.debrief and result.three_things == sample.three_things
    assert (result.key, result.variant, result.severity) == (sample.key, 1, sample.severity)


def test_correct_slow_hits_floor(sample: Drill, scoring: ScoringRules) -> None:
    assert grade(sample, "cup-may", scoring.slow_seconds).score == scoring.min_correct_score
    assert grade(sample, "cup-may", scoring.slow_seconds * 10).score == scoring.min_correct_score


def test_correct_midway_is_linear(scoring: ScoringRules) -> None:
    mid = (scoring.fast_seconds + scoring.slow_seconds) / 2
    expected = round((MAX_SCORE + scoring.min_correct_score) / 2)
    assert answer_score(True, mid, scoring) == expected
    quarter = scoring.fast_seconds + (scoring.slow_seconds - scoring.fast_seconds) / 4
    assert scoring.min_correct_score < answer_score(True, quarter, scoring) < MAX_SCORE


def test_wrong_answer(sample: Drill, scoring: ScoringRules) -> None:
    result = grade(sample, "chuyen-tien", 3)
    assert result.score == scoring.wrong_score and not result.correct
    assert result.debrief and len(result.three_things) == 3


def test_negative_seconds_clamped(sample: Drill) -> None:
    assert grade(sample, "cup-may", -5).seconds == 0.0


def test_unknown_option_raises(sample: Drill) -> None:
    with pytest.raises(ValidationFailed) as exc:
        grade(sample, "khong-co", 1)
    assert exc.value.code == OPTION_NOT_FOUND and exc.value.status == 422
    assert exc.value.details == {"key": sample.key, "option_id": "khong-co"}


def test_custom_rules(sample: Drill) -> None:
    custom = ScoringRules(fast_seconds=0, slow_seconds=1, min_correct_score=50, wrong_score=10)
    rules = load_rules().model_copy(update={"scoring": custom})
    assert grade(sample, "cup-may", 0.5, rules).score == 75
    assert grade(sample, "chuyen-tien", 0.5, rules).score == 10


def test_vulnerability_before_after(sample: Drill) -> None:
    before = grade(sample, "chuyen-tien", 20)
    after = grade(sample, "cup-may", 8)
    assert vulnerability_score([before]) == 100.0
    assert vulnerability_score([after]) == 0.0
    assert vulnerability_score([]) == 100.0


def test_vulnerability_is_severity_weighted() -> None:
    light = make_grade()
    heavy = make_grade(severity=3, score=0, correct=False)
    assert vulnerability_score([light, heavy]) == 75.0
    assert vulnerability_score([light, make_grade(score=50)]) == 25.0


def test_grade_bounds() -> None:
    with pytest.raises(ValidationError):
        make_grade(score=101)
    with pytest.raises(ValidationError):
        make_grade(seconds=-1)
