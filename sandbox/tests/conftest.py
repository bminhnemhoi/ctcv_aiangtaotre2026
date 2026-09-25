"""Shared fixtures for ctcv-sandbox tests."""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ctcv_core.paths import SCENARIOS_DIR
from ctcv_sandbox.schema import Scenario

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
INVALID_DIR = FIXTURES_DIR / "invalid"
SAMPLE_ID = "chuyen-khoan-qr"
WriteJson = Callable[[Path, Any], Path]
SAMPLE_PATH = SCENARIOS_DIR / f"{SAMPLE_ID}.json"


@pytest.fixture(scope="session")
def sample_data() -> dict[str, Any]:
    """The shipped sample scenario as raw JSON (read once, never mutated)."""
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def sample_dict(sample_data: dict[str, Any]) -> dict[str, Any]:
    """A deep copy of the sample JSON that a test may mutate freely."""
    return copy.deepcopy(sample_data)


@pytest.fixture(scope="session")
def sample(sample_data: dict[str, Any]) -> Scenario:
    """The shipped sample scenario as a parsed model."""
    return Scenario.model_validate(sample_data)


@pytest.fixture
def scenarios_dir(tmp_path: Path) -> Path:
    """A throw-away scenarios directory holding a copy of the sample (+ a README)."""
    target = tmp_path / "scenarios"
    target.mkdir()
    shutil.copy(SAMPLE_PATH, target / SAMPLE_PATH.name)
    (target / "README.md").write_text("# not a scenario\n", encoding="utf-8")
    return target


@pytest.fixture
def write_json() -> WriteJson:
    """Return a helper that writes ``data`` as UTF-8 JSON and returns the path."""

    def _write(path: Path, data: Any) -> Path:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    return _write
