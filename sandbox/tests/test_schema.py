from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ctcv_core.config import load_config
from ctcv_sandbox.schema import (
    REQUIRED_NEVER_ASK,
    Colour,
    Element,
    ElementKind,
    InputAction,
    Mistake,
    Scenario,
    Screen,
    SkillGroup,
    Success,
    TapAction,
)


def test_skill_groups_match_app_config() -> None:
    assert [g.value for g in SkillGroup] == load_config("app")["skill_groups"]
    assert len(SkillGroup) == 5


def test_element_and_colour_enums() -> None:
    assert {k.value for k in ElementKind} == {"button", "input", "text", "banner"}
    assert {c.value for c in Colour} == {"xanh", "do", "vang", "xam", "trang"}


def test_sample_parses(sample: Scenario) -> None:
    assert sample.id == "chuyen-khoan-qr"
    assert sample.skill_group is SkillGroup.THANH_TOAN_THUE_SO
    assert sample.level == 1
    assert len(sample.screens) >= 5
    assert sample.start_screen == "home"
    assert sample.success.screen == "done"
    assert set(REQUIRED_NEVER_ASK) <= set(sample.never_ask)


@pytest.mark.parametrize("bad_id", ["Chuyen-Khoan", "chuyen_khoan", "-abc", "abc-", "a b"])
def test_slug_pattern_rejected(sample_dict: dict[str, Any], bad_id: str) -> None:
    sample_dict["id"] = bad_id
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(sample_dict)
    assert exc.value.errors()[0]["type"] == "string_pattern_mismatch"


@pytest.mark.parametrize("level", [0, 4, -1])
def test_level_range(sample_dict: dict[str, Any], level: int) -> None:
    sample_dict["level"] = level
    with pytest.raises(ValidationError):
        Scenario.model_validate(sample_dict)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_level_ok(sample_dict: dict[str, Any], level: int) -> None:
    sample_dict["level"] = level
    assert Scenario.model_validate(sample_dict).level == level


def test_app_label_must_say_simulated(sample_dict: dict[str, Any]) -> None:
    sample_dict["app_label"] = "Ứng dụng ngân hàng"
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(sample_dict)
    err = exc.value.errors()[0]
    assert err["type"] == "app_label_not_simulated"
    assert "mô phỏng" in err["msg"]


def test_app_label_case_insensitive(sample_dict: dict[str, Any]) -> None:
    sample_dict["app_label"] = "ỨNG DỤNG MÔ PHỎNG"
    assert Scenario.model_validate(sample_dict)


@pytest.mark.parametrize("never_ask", [["otp"], ["mat_khau"], ["so_the", "cccd"]])
def test_never_ask_requires_otp_and_password(
    sample_dict: dict[str, Any], never_ask: list[str]
) -> None:
    sample_dict["never_ask"] = never_ask
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(sample_dict)
    assert exc.value.errors()[0]["type"] == "never_ask_incomplete"


def test_unknown_field_rejected(sample_dict: dict[str, Any]) -> None:
    sample_dict["ghi_chu"] = "x"
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(sample_dict)
    assert exc.value.errors()[0]["type"] == "extra_forbidden"


def test_action_union_discriminates() -> None:
    screen = Screen.model_validate(
        {
            "id": "s",
            "title": "S",
            "coach_line": "Bác bấm nút xanh nhé.",
            "valid_actions": [
                {"tap": "btn", "next": "t"},
                {"input": "amount", "next": "t"},
            ],
        }
    )
    tap, typed = screen.valid_actions
    assert isinstance(tap, TapAction) and tap.tap == "btn"
    assert isinstance(typed, InputAction) and typed.value_pattern == r"^.+$"


def test_screen_and_scenario_lookup(sample: Scenario) -> None:
    home = sample.screen("home")
    assert home is not None and home.title
    assert home.element("btn_qr") is not None
    assert home.element("khong_co") is None
    assert sample.screen("khong_co") is None


def test_duplicate_ids_first_wins() -> None:
    a = Element(id="btn", kind=ElementKind.BUTTON, label="A")
    b = Element(id="btn", kind=ElementKind.BUTTON, label="B")
    screen = Screen(id="s", title="S", elements=[a, b], coach_line="Bấm nút nhé.")
    assert screen.element("btn") is a
    dup = Screen(id="s", title="S2", coach_line="Khác.", terminal=True)
    scenario = Scenario(
        id="x",
        skill_group=SkillGroup.AN_TOAN_SO,
        level=1,
        version="1.0.0",
        app_label="Ứng dụng mô phỏng",
        goal="g",
        intent_confirmation="Bác muốn gì?",
        start_screen="s",
        screens=[screen, dup],
        success=Success(screen="s"),
        never_ask=["otp", "mat_khau"],
    )
    assert scenario.screen("s") is screen


def test_text_length_limit() -> None:
    with pytest.raises(ValidationError):
        Mistake(tap="btn", hint="x" * 201)
    with pytest.raises(ValidationError):
        Element(id="e", kind=ElementKind.TEXT, label="")
