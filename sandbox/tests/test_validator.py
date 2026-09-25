from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ctcv_core.config import load_config
from ctcv_core.paths import SCENARIOS_DIR
from ctcv_sandbox.schema import Element, ElementKind, Scenario
from ctcv_sandbox.validator import (
    Code,
    Issue,
    Rules,
    issues_from_validation_error,
    join_loc,
    load_rules,
    looks_sensitive,
    validate,
    validate_data,
    validate_file,
)

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"
SAMPLE_ID = "chuyen-khoan-qr"
SAMPLE_PATH = SCENARIOS_DIR / f"{SAMPLE_ID}.json"
WriteJson = Callable[[Path, Any], Path]


INVALID_FIXTURES = sorted(INVALID_DIR.glob("*.json"))
MIN_INVALID_FIXTURES = 8


def expected_code(path: Path) -> str:
    return path.stem.upper().replace("-", "_")


def codes_of(issues: list[Issue]) -> set[str]:
    return {issue.code for issue in issues}


def test_sample_scenario_is_valid(sample: Scenario) -> None:
    assert validate(sample) == []
    assert validate_file(SAMPLE_PATH) == []


def test_enough_invalid_fixtures() -> None:
    assert len(INVALID_FIXTURES) >= MIN_INVALID_FIXTURES


@pytest.mark.parametrize("path", INVALID_FIXTURES, ids=lambda p: p.stem)
def test_invalid_fixture_breaks_exactly_one_rule(path: Path) -> None:
    issues = validate_file(path)
    assert codes_of(issues) == {expected_code(path)}, [str(i) for i in issues]
    for issue in issues:
        assert issue.message.strip()
        assert issue.code in set(Code)


def test_every_fixture_code_is_a_known_code() -> None:
    assert {expected_code(p) for p in INVALID_FIXTURES} <= set(Code)


def test_no_terminal_screen(sample_dict: dict[str, Any]) -> None:
    for screen in sample_dict["screens"]:
        screen["terminal"] = False
    sample_dict["screens"][-1]["valid_actions"] = [{"tap": "btn_home", "next": "home"}]
    assert Code.NO_TERMINAL_SCREEN in codes_of(validate_data(sample_dict))


def test_reachability_uses_only_known_edges(sample_dict: dict[str, Any]) -> None:
    """A dangling ``next`` must not crash BFS and only yields ACTION_SCREEN_MISSING."""
    sample_dict["screens"][-1]["valid_actions"] = [{"tap": "btn_home", "next": "khong_co"}]
    assert codes_of(validate_data(sample_dict)) == {Code.ACTION_SCREEN_MISSING}


def test_validate_data_rejects_non_object() -> None:
    assert codes_of(validate_data([1, 2])) == {Code.NOT_AN_OBJECT}
    assert codes_of(validate_data("x")) == {Code.NOT_AN_OBJECT}


def test_validate_file_missing(tmp_path: Path) -> None:
    assert codes_of(validate_file(tmp_path / "nope.json")) == {Code.FILE_NOT_FOUND}


def test_validate_file_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert codes_of(validate_file(path)) == {Code.JSON_INVALID}


def test_validate_file_id_must_match_stem(
    tmp_path: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    path = write_json(tmp_path / "ten-khac.json", sample_dict)
    issues = validate_file(path)
    assert codes_of(issues) == {Code.ID_FILENAME_MISMATCH}
    assert "ten-khac" in issues[0].message


def test_unmapped_pydantic_error_falls_back_to_schema_invalid(
    sample_dict: dict[str, Any],
) -> None:
    sample_dict["level"] = "một"
    assert codes_of(validate_data(sample_dict)) == {Code.SCHEMA_INVALID}


def test_nested_pattern_error_is_ident_invalid(sample_dict: dict[str, Any]) -> None:
    sample_dict["screens"][0]["elements"][0]["id"] = "Sai-Id"
    issues = validate_data(sample_dict)
    assert codes_of(issues) == {Code.IDENT_INVALID}
    assert issues[0].path == "screens[0].elements[0].id"


def test_issues_from_validation_error_direct(sample_dict: dict[str, Any]) -> None:
    del sample_dict["goal"]
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(sample_dict)
    issues = issues_from_validation_error(exc.value)
    assert [(i.code, i.path) for i in issues] == [(Code.FIELD_MISSING, "goal")]
    assert issues[0].message.startswith("Trường không hợp lệ")


def test_issue_str_and_join_loc() -> None:
    assert str(Issue(code="X", message="m", path="a.b")) == "[X] a.b: m"
    assert str(Issue(code="X", message="m")) == "[X] m"
    assert join_loc(("screens", 0, "elements", 1, "id")) == "screens[0].elements[1].id"
    assert join_loc(()) == ""


def test_rules_come_from_guardrails_config() -> None:
    cfg = load_config("guardrails")
    rules = load_rules()
    assert rules.max_sentences == cfg["max_sentences"]
    assert rules.banned_terms == cfg["banned_terms"]


def test_custom_rules_are_honoured(sample: Scenario) -> None:
    strict = Rules(max_sentences=0, banned_terms=["Quét"])
    codes = codes_of(validate(sample, strict))
    assert {Code.COACH_LINE_TOO_LONG, Code.COACH_LINE_BANNED_TERM} <= codes


@pytest.mark.parametrize(
    ("element_id", "label", "expected"),
    [
        ("otp", "Mã", True),
        ("ma_otp", "Mã xác nhận", True),
        ("pw", "Mật khẩu", True),
        ("so_the", "Số thẻ", True),
        ("amount", "Số tiền", False),
        ("otpx", "Mã", False),
    ],
)
def test_looks_sensitive(element_id: str, label: str, expected: bool) -> None:
    element = Element(id=element_id, kind=ElementKind.INPUT, label=label)
    assert looks_sensitive(element, ["otp", "mat_khau", "so_the"]) is expected


def test_fixture_files_are_well_formed_json() -> None:
    for path in INVALID_FIXTURES:
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict), path.name
