"""``config/schemas/scenario.schema.json`` must equal what ``scripts/gen_schemas.py`` emits."""

from __future__ import annotations

import importlib.util
import json
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ctcv_core.paths import REPO_ROOT, SCHEMAS_DIR
from ctcv_sandbox.schema import Scenario

SCHEMA_PATH = SCHEMAS_DIR / "scenario.schema.json"


@pytest.fixture(scope="module")
def gen_schemas() -> ModuleType:
    script = REPO_ROOT / "scripts" / "gen_schemas.py"
    spec = importlib.util.spec_from_file_location("gen_schemas", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_file_is_up_to_date(gen_schemas: ModuleType) -> None:
    assert SCHEMA_PATH.is_file(), "chạy `make schemas`"
    assert SCHEMA_PATH.read_text(encoding="utf-8") == gen_schemas.render_schema(Scenario)


def test_schema_file_is_valid_2020_12() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["$defs"]) >= {"Screen", "Element", "TapAction", "InputAction", "SkillGroup"}


def test_sample_validates_against_schema_file(sample_data: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(sample_data)
