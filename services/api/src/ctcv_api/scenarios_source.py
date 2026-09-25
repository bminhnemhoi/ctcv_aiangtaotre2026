"""Scenario listing adapter for ``GET /v1/scenarios``.

Prefers the sandbox package (``ctcv_sandbox.loader.list_scenarios() -> list[Scenario]``,
brief §5). When that package is not importable yet, falls back to reading
``sandbox/scenarios/*.json`` directly with a minimal pydantic validation of the
five fields the API exposes. An explicit ``directory`` always uses the fallback
reader (tests point it at fixtures).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ctcv_api.schemas import ScenarioSummary
from ctcv_core import paths

log = logging.getLogger(__name__)

SLUG_PATTERN = r"^[a-z0-9-]+$"
LEVEL_MIN, LEVEL_MAX = 1, 3


class ScenarioLike(Protocol):
    """The subset of ``ctcv_sandbox.schema.Scenario`` the API needs."""

    id: str
    skill_group: str
    level: int
    goal: str
    version: str


class ScenarioLite(BaseModel):
    """Minimal validated view of a scenario JSON file (other fields ignored)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=SLUG_PATTERN)
    skill_group: str = Field(min_length=1)
    level: int = Field(ge=LEVEL_MIN, le=LEVEL_MAX)
    goal: str = Field(min_length=1)
    version: str = Field(min_length=1)


def sandbox_loader() -> Callable[[], Sequence[Any]] | None:
    """Return ``ctcv_sandbox.loader.list_scenarios`` when the sandbox package provides it."""
    try:
        from ctcv_sandbox.loader import list_scenarios
    except (ImportError, AttributeError):
        return None
    return list_scenarios


def read_scenario_dir(directory: Path) -> list[ScenarioLite]:
    """Read every ``*.json`` in ``directory``; skip (and log) files that do not validate."""
    items: list[ScenarioLite] = []
    if not directory.is_dir():
        log.warning("scenario directory missing", extra={"dir": str(directory)})
        return items
    for path in sorted(directory.glob("*.json")):
        try:
            items.append(ScenarioLite.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            log.warning(
                "scenario file skipped",
                extra={"file": path.name, "reason": type(exc).__name__},
            )
    return items


def load_scenarios(directory: Path | None = None) -> Sequence[ScenarioLike]:
    """Return scenarios from ``directory``, else from ctcv_sandbox, else the default dir."""
    if directory is not None:
        return read_scenario_dir(directory)
    loader = sandbox_loader()
    if loader is not None:
        return list(loader())
    return read_scenario_dir(paths.SCENARIOS_DIR)


def to_summary(scenario: ScenarioLike) -> ScenarioSummary:
    """Project any scenario-like object onto the API's ``ScenarioSummary``."""
    return ScenarioSummary(
        id=scenario.id,
        skill_group=scenario.skill_group,
        level=scenario.level,
        goal=scenario.goal,
        version=scenario.version,
    )


def list_scenario_summaries(
    *,
    skill: str | None = None,
    level: int | None = None,
    directory: Path | None = None,
) -> list[ScenarioSummary]:
    """List scenarios filtered by ``skill`` (skill_group) and ``level``, sorted by level then id."""
    summaries = [
        to_summary(scenario)
        for scenario in load_scenarios(directory)
        if (skill is None or scenario.skill_group == skill)
        and (level is None or scenario.level == level)
    ]
    return sorted(summaries, key=lambda item: (item.level, item.id))
