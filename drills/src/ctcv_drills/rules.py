"""Authoring/scoring rules for drills, loaded from the packaged ``rules.yaml``.

Keeping limits and block lists in data (not code) lets reviewers extend the real-name
list or tune word limits without touching Python; every regex is compiled once.
"""

from __future__ import annotations

import re
from functools import cached_property, lru_cache
from importlib import resources

import yaml
from pydantic import BaseModel, ConfigDict, Field

RULES_FILENAME = "rules.yaml"


class ScoringRules(BaseModel):
    """Parameters of :func:`ctcv_drills.scoring.grade`."""

    model_config = ConfigDict(extra="forbid")

    fast_seconds: float = Field(ge=0)
    slow_seconds: float = Field(gt=0)
    min_correct_score: int = Field(ge=0, le=100)
    wrong_score: int = Field(ge=0, le=100)


class DrillRules(BaseModel):
    """Validated content of ``rules.yaml`` with compiled regexes."""

    model_config = ConfigDict(extra="forbid")

    version: int
    utterance_max_words: int = Field(gt=0)
    pretext_max_words: int = Field(gt=0)
    max_string_chars: int = Field(gt=0)
    min_digit_run: int = Field(ge=2)
    forbidden_fields: list[str] = Field(min_length=1)
    url_pattern: str
    phone_pattern: str
    real_names: list[str] = Field(min_length=1)
    escalation_markers: list[str]
    escalation_patterns: list[str]
    scoring: ScoringRules

    @cached_property
    def url_re(self) -> re.Pattern[str]:
        """Compiled URL/domain pattern."""
        return re.compile(self.url_pattern)

    @cached_property
    def phone_re(self) -> re.Pattern[str]:
        """Compiled Vietnamese phone-number pattern."""
        return re.compile(self.phone_pattern)

    @cached_property
    def digit_run_re(self) -> re.Pattern[str]:
        """``min_digit_run`` digits, single separators allowed (account numbers, amounts)."""
        return re.compile(rf"\d(?:[\s.,-]?\d){{{self.min_digit_run - 1},}}")

    @cached_property
    def escalation_res(self) -> list[re.Pattern[str]]:
        """Compiled multi-turn/escalation patterns."""
        return [re.compile(p) for p in self.escalation_patterns]

    @cached_property
    def forbidden_field_set(self) -> frozenset[str]:
        """Case-folded forbidden field names."""
        return frozenset(name.casefold() for name in self.forbidden_fields)


@lru_cache(maxsize=1)
def load_rules() -> DrillRules:
    """Read and validate the packaged ``rules.yaml`` (cached)."""
    text = resources.files("ctcv_drills").joinpath(RULES_FILENAME).read_text(encoding="utf-8")
    return DrillRules.model_validate(yaml.safe_load(text))
