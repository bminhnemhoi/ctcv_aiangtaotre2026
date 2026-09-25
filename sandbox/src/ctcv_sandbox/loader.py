"""Load scenarios from ``sandbox/scenarios/*.json`` and compute their checksum."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ctcv_core.errors import NotFound, ValidationFailed
from ctcv_core.paths import SCENARIOS_DIR
from ctcv_sandbox.schema import Scenario

SCENARIO_NOT_FOUND = "SCENARIO_NOT_FOUND"
SCENARIO_INVALID = "SCENARIO_INVALID"
NOT_FOUND_MESSAGE = "Không tìm thấy bài học này, bác thử chọn bài khác nhé."
INVALID_MESSAGE = "Bài học này đang lỗi, bác thử chọn bài khác nhé."


def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON file; raise ``ValidationFailed`` (SCENARIO_INVALID) on bad JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationFailed(
            INVALID_MESSAGE, code=SCENARIO_INVALID, details={"path": path.name, "error": str(exc)}
        ) from exc


def parse_scenario(data: Mapping[str, Any], source: str = "") -> Scenario:
    """Build a :class:`Scenario`; raise ``ValidationFailed`` (SCENARIO_INVALID) on schema errors."""
    try:
        return Scenario.model_validate(data)
    except ValidationError as exc:
        raise ValidationFailed(
            INVALID_MESSAGE,
            code=SCENARIO_INVALID,
            details={"source": source, "errors": [e["msg"] for e in exc.errors()]},
        ) from exc


def scenario_files(dir: Path = SCENARIOS_DIR) -> list[Path]:
    """Return every ``*.json`` file in ``dir`` sorted by name (README and others ignored)."""
    return sorted(p for p in dir.glob("*.json") if p.is_file())


def list_scenarios(dir: Path = SCENARIOS_DIR) -> list[Scenario]:
    """Load every scenario in ``dir`` sorted by id (schema-validated, not graph-validated)."""
    scenarios = [parse_scenario(read_json(path), path.name) for path in scenario_files(dir)]
    return sorted(scenarios, key=lambda s: s.id)


def load_scenario(scenario_id: str, dir: Path = SCENARIOS_DIR) -> Scenario:
    """Load ``<dir>/<scenario_id>.json``; raise ``NotFound`` (SCENARIO_NOT_FOUND) if absent."""
    path = dir / f"{scenario_id}.json"
    if not path.is_file():
        raise NotFound(NOT_FOUND_MESSAGE, code=SCENARIO_NOT_FOUND, details={"id": scenario_id})
    scenario = parse_scenario(read_json(path), path.name)
    if scenario.id != scenario_id:
        raise ValidationFailed(
            INVALID_MESSAGE,
            code=SCENARIO_INVALID,
            details={"id": scenario_id, "file_id": scenario.id},
        )
    return scenario


def canonical_json(scenario: Scenario) -> str:
    """Serialise deterministically (sorted keys, compact separators, UTF-8 preserved)."""
    payload = scenario.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checksum(scenario: Scenario) -> str:
    """SHA-256 hex digest of the canonical JSON (stored in the ``scenarios`` table)."""
    return hashlib.sha256(canonical_json(scenario).encode("utf-8")).hexdigest()
