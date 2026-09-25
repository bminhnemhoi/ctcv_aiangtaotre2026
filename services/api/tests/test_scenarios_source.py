"""Scenario adapter: sandbox package when present, JSON fallback otherwise."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ctcv_api import scenarios_source
from ctcv_api.scenarios_source import (
    ScenarioLite,
    list_scenario_summaries,
    load_scenarios,
    read_scenario_dir,
    sandbox_loader,
)
from ctcv_core import paths

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scenarios"


def test_fallback_reads_valid_files_and_skips_broken_ones(caplog):
    with caplog.at_level(logging.WARNING, logger="ctcv_api.scenarios_source"):
        items = read_scenario_dir(FIXTURES)
    assert [item.id for item in items] == ["chuyen-khoan-qr", "dang-nhap-vneid"]
    assert all(isinstance(item, ScenarioLite) for item in items)
    skipped = {record.__dict__.get("file") for record in caplog.records}
    assert skipped == {"broken.json", "missing-fields.json"}


def test_missing_directory_is_empty_not_an_error(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert read_scenario_dir(tmp_path / "nowhere") == []
    assert "scenario directory missing" in caplog.text


def test_explicit_directory_bypasses_sandbox_package(monkeypatch):
    fake = SimpleNamespace(list_scenarios=lambda: [_scenario("from-sandbox")])
    monkeypatch.setitem(sys.modules, "ctcv_sandbox.loader", fake)
    ids = [item.id for item in load_scenarios(FIXTURES)]
    assert ids == ["chuyen-khoan-qr", "dang-nhap-vneid"]


def test_sandbox_loader_is_used_when_available(monkeypatch):
    fake = SimpleNamespace(list_scenarios=lambda: [_scenario("from-sandbox", level=3)])
    monkeypatch.setitem(sys.modules, "ctcv_sandbox.loader", fake)
    assert sandbox_loader() is fake.list_scenarios
    summaries = list_scenario_summaries()
    assert [(s.id, s.level) for s in summaries] == [("from-sandbox", 3)]


def test_sandbox_missing_falls_back_to_default_directory(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctcv_sandbox.loader", None)
    monkeypatch.setattr(paths, "SCENARIOS_DIR", FIXTURES)
    assert sandbox_loader() is None
    assert [s.id for s in list_scenario_summaries()] == ["chuyen-khoan-qr", "dang-nhap-vneid"]


def test_sandbox_module_without_function_falls_back(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctcv_sandbox.loader", SimpleNamespace())
    assert sandbox_loader() is None


def test_filters_and_ordering():
    scenarios = [
        _scenario("b-level-2", level=2),
        _scenario("a-level-2", level=2, skill="an-toan-so"),
        _scenario("z-level-1", level=1),
    ]
    fake = SimpleNamespace(list_scenarios=lambda: scenarios)
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "ctcv_sandbox.loader", fake)
        everything = list_scenario_summaries()
        by_level = list_scenario_summaries(level=2)
        by_skill = list_scenario_summaries(skill="an-toan-so")
        both = list_scenario_summaries(skill="an-toan-so", level=1)
    assert [s.id for s in everything] == ["z-level-1", "a-level-2", "b-level-2"]
    assert [s.id for s in by_level] == ["a-level-2", "b-level-2"]
    assert [s.id for s in by_skill] == ["a-level-2"]
    assert both == []


def test_scenario_lite_rejects_bad_slug_and_level():
    with pytest.raises(ValueError):
        ScenarioLite(id="Bad Slug", skill_group="x", level=1, goal="g", version="1")
    with pytest.raises(ValueError):
        ScenarioLite(id="ok", skill_group="x", level=4, goal="g", version="1")


def test_module_reads_default_dir_from_ctcv_core_paths():
    assert scenarios_source.paths.SCENARIOS_DIR == paths.SCENARIOS_DIR


def _scenario(scenario_id: str, *, level: int = 1, skill: str = "thanh-toan-thue-so"):
    return SimpleNamespace(
        id=scenario_id, skill_group=skill, level=level, goal="Mục tiêu", version="1.0.0"
    )
