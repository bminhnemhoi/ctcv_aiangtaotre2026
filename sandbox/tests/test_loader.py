from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ctcv_core.errors import NotFound, ValidationFailed
from ctcv_core.paths import SCENARIOS_DIR
from ctcv_sandbox.loader import (
    SCENARIO_INVALID,
    SCENARIO_NOT_FOUND,
    canonical_json,
    checksum,
    list_scenarios,
    load_scenario,
    scenario_files,
)
from ctcv_sandbox.schema import Scenario

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"
SAMPLE_ID = "chuyen-khoan-qr"
SAMPLE_PATH = SCENARIOS_DIR / f"{SAMPLE_ID}.json"
WriteJson = Callable[[Path, Any], Path]


def test_default_dir_lists_the_sample() -> None:
    ids = [s.id for s in list_scenarios()]
    assert SAMPLE_ID in ids and ids == sorted(ids)


def test_scenario_files_ignores_non_json(scenarios_dir: Path) -> None:
    assert [p.name for p in scenario_files(scenarios_dir)] == [f"{SAMPLE_ID}.json"]


def test_load_scenario(scenarios_dir: Path) -> None:
    scenario = load_scenario(SAMPLE_ID, scenarios_dir)
    assert isinstance(scenario, Scenario) and scenario.id == SAMPLE_ID


def test_load_scenario_not_found(scenarios_dir: Path) -> None:
    with pytest.raises(NotFound) as exc:
        load_scenario("khong-co", scenarios_dir)
    assert exc.value.code == SCENARIO_NOT_FOUND and exc.value.status == 404
    assert exc.value.to_response()["error"]["details"] == {"id": "khong-co"}


def test_load_scenario_bad_json(scenarios_dir: Path) -> None:
    (scenarios_dir / "hong.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValidationFailed) as exc:
        load_scenario("hong", scenarios_dir)
    assert exc.value.code == SCENARIO_INVALID and exc.value.status == 422


def test_load_scenario_schema_error(
    scenarios_dir: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    sample_dict["id"] = "sai-schema"
    sample_dict["level"] = 9
    write_json(scenarios_dir / "sai-schema.json", sample_dict)
    with pytest.raises(ValidationFailed) as exc:
        load_scenario("sai-schema", scenarios_dir)
    assert exc.value.code == SCENARIO_INVALID
    assert exc.value.details is not None and exc.value.details["errors"]


def test_load_scenario_id_mismatch(
    scenarios_dir: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    write_json(scenarios_dir / "ten-khac.json", sample_dict)
    with pytest.raises(ValidationFailed) as exc:
        load_scenario("ten-khac", scenarios_dir)
    assert exc.value.details == {"id": "ten-khac", "file_id": SAMPLE_ID}


def test_list_scenarios_propagates_errors(scenarios_dir: Path) -> None:
    (scenarios_dir / "hong.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValidationFailed):
        list_scenarios(scenarios_dir)


def test_checksum_is_stable_and_sensitive(sample: Scenario, sample_dict: dict[str, Any]) -> None:
    digest = checksum(sample)
    assert len(digest) == 64 and int(digest, 16) >= 0
    assert checksum(Scenario.model_validate(sample_dict)) == digest
    sample_dict["goal"] = "Mục tiêu khác"
    assert checksum(Scenario.model_validate(sample_dict)) != digest


def test_canonical_json_is_sorted_compact_utf8(sample: Scenario) -> None:
    text = canonical_json(sample)
    compact = json.dumps(
        json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert text == compact and text.startswith('{"app_label":')
    assert "mô phỏng" in text
