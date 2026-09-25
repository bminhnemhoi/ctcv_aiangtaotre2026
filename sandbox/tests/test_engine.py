from __future__ import annotations

from typing import Any

import pytest

from ctcv_core.errors import ValidationFailed
from ctcv_core.logging import DEFAULT_REDACTION
from ctcv_sandbox.engine import (
    INVALID_INPUT_LEAD,
    WRONG_TAP_LEAD,
    Feedback,
    FeedbackCode,
    State,
    apply,
    generic_hint,
    highlight_of,
    start,
    storable_value,
    succeeded,
    value_matches,
)
from ctcv_sandbox.events import SessionEvent
from ctcv_sandbox.schema import Scenario, Screen

HAPPY_PATH = (
    SessionEvent.tap("btn_qr"),
    SessionEvent.tap("btn_capture"),
    SessionEvent.typed("amount", "200000"),
    SessionEvent.tap("btn_confirm"),
)


def walk(scenario: Scenario, state: State, *events: SessionEvent) -> tuple[State, Feedback]:
    feedback = Feedback(code=FeedbackCode.OK, say="")
    for event in events:
        state, feedback = apply(scenario, state, event)
    return state, feedback


def test_start(sample: Scenario) -> None:
    state = start(sample)
    assert state == State(scenario_id="chuyen-khoan-qr", screen_id="home")
    assert state.steps == state.mistakes == state.hints_used == 0
    assert not state.done and not state.success and state.values == {}


def test_happy_path(sample: Scenario) -> None:
    state = start(sample)
    state, fb = apply(sample, state, SessionEvent.tap("btn_qr"))
    assert (state.screen_id, fb.code, fb.highlight) == ("scan", FeedbackCode.OK, "btn_capture")
    assert fb.say == sample.screen("scan").coach_line and not fb.mistake
    state, fb = apply(sample, state, SessionEvent.tap("btn_capture"))
    assert (state.screen_id, fb.highlight) == ("amount", "amount")
    state, fb = apply(sample, state, SessionEvent.typed("amount", "200000"))
    assert (state.screen_id, state.values) == ("confirm", {"amount": "200000"})
    state, fb = apply(sample, state, SessionEvent.tap("btn_confirm"))
    assert state.screen_id == "done"
    assert state.done and state.success and fb.done and fb.code is FeedbackCode.DONE
    assert fb.highlight is None
    assert (state.steps, state.mistakes, state.hints_used) == (4, 0, 0)
    assert state.history == ["home", "scan", "amount", "confirm"]


def test_known_mistake_gives_hint_and_counts(sample: Scenario) -> None:
    state, fb = apply(sample, start(sample), SessionEvent.tap("btn_promo"))
    expected_hint = sample.screen("home").common_mistakes[0].hint
    assert fb.code is FeedbackCode.KNOWN_MISTAKE
    assert fb.mistake and fb.hint == expected_hint and fb.say == expected_hint
    assert fb.highlight == "btn_qr" and not fb.done
    assert state.screen_id == "home"
    assert (state.steps, state.mistakes, state.hints_used) == (1, 1, 1)


def test_unknown_and_wrong_element_taps(sample: Scenario) -> None:
    state, fb = apply(sample, start(sample), SessionEvent.tap("btn_khong_co"))
    assert fb.code is FeedbackCode.UNKNOWN_ELEMENT and fb.mistake
    assert fb.hint is not None and fb.hint.startswith(WRONG_TAP_LEAD)
    assert sample.screen("home").coach_line in fb.hint
    state, fb = apply(sample, state, SessionEvent.tap("txt_balance"))
    assert fb.code is FeedbackCode.WRONG_ELEMENT and state.mistakes == 2


def test_mistake_then_recover(sample: Scenario) -> None:
    events = [
        SessionEvent.tap("btn_promo"),
        SessionEvent.tap("btn_qr"),
        SessionEvent.tap("btn_gallery"),
        SessionEvent.tap("btn_capture"),
        SessionEvent.typed("amount", "200000"),
        SessionEvent.tap("btn_cancel"),
        SessionEvent.tap("btn_confirm"),
    ]
    state, fb = walk(sample, start(sample), *events)
    assert state.done and state.success and fb.done
    assert (state.steps, state.mistakes, state.hints_used) == (7, 3, 3)


def test_wrong_input_value(sample: Scenario) -> None:
    state, _ = walk(sample, start(sample), *HAPPY_PATH[:2])
    for bad in ("abc", "12", "0200000", ""):
        state, fb = apply(sample, state, SessionEvent.typed("amount", bad))
        assert fb.code is FeedbackCode.INVALID_INPUT and fb.mistake
        assert fb.hint is not None and fb.hint.startswith(INVALID_INPUT_LEAD)
        assert state.screen_id == "amount" and "amount" not in state.values
    assert state.mistakes == 4


def test_valid_input_but_wrong_amount_fails_success(sample: Scenario) -> None:
    events = [*HAPPY_PATH[:2], SessionEvent.typed("amount", "300000"), HAPPY_PATH[3]]
    state, fb = walk(sample, start(sample), *events)
    assert state.done and fb.done and not state.success


def test_input_on_non_input_element_is_a_mistake(sample: Scenario) -> None:
    state, fb = apply(sample, start(sample), SessionEvent.typed("btn_qr", "x"))
    assert fb.code is FeedbackCode.WRONG_ELEMENT and fb.mistake and state.screen_id == "home"
    state, fb = apply(sample, state, SessionEvent.typed("amount", "1"))
    assert fb.code is FeedbackCode.UNKNOWN_ELEMENT


def test_back(sample: Scenario) -> None:
    initial = start(sample)
    state, fb = apply(sample, initial, SessionEvent.back())
    assert state == initial and fb.code is FeedbackCode.BACK and fb.highlight == "btn_qr"
    state, _ = apply(sample, state, SessionEvent.tap("btn_qr"))
    state, fb = apply(sample, state, SessionEvent.back())
    assert state.screen_id == "home" and state.history == [] and state.steps == 2
    assert fb.code is FeedbackCode.BACK and fb.say == sample.screen("home").coach_line


def test_ask_repeats_coach_line_and_counts_hint(sample: Scenario) -> None:
    state, fb = apply(sample, start(sample), SessionEvent.ask("Cháu ơi bấm đâu?"))
    assert fb.code is FeedbackCode.ASK and fb.hint == fb.say == sample.screen("home").coach_line
    assert (state.steps, state.mistakes, state.hints_used) == (0, 0, 1)
    assert not fb.mistake


def test_events_after_done_are_ignored(sample: Scenario) -> None:
    done, _ = walk(sample, start(sample), *HAPPY_PATH)
    after, fb = apply(sample, done, SessionEvent.tap("btn_home"))
    assert after == done and fb.code is FeedbackCode.ALREADY_DONE and fb.done


def test_apply_never_mutates_input_state(sample: Scenario) -> None:
    state = start(sample)
    snapshot = state.model_copy(deep=True)
    apply(sample, state, SessionEvent.tap("btn_promo"))
    apply(sample, state, SessionEvent.tap("btn_qr"))
    assert state == snapshot


def test_missing_screen_raises_app_error(sample: Scenario) -> None:
    broken = State(scenario_id=sample.id, screen_id="khong_co")
    with pytest.raises(ValidationFailed) as exc:
        apply(sample, broken, SessionEvent.back())
    assert exc.value.code == "SCENARIO_INVALID" and exc.value.status == 422


def sensitive_scenario(sample_dict: dict[str, Any]) -> Scenario:
    amount = next(s for s in sample_dict["screens"] if s["id"] == "amount")
    amount["elements"].append({"id": "otp", "kind": "input", "label": "Mã OTP", "sensitive": True})
    amount["elements"].append({"id": "pin", "kind": "input", "label": "Mã PIN"})
    amount["valid_actions"].append({"input": "otp", "value_pattern": r"^\d{6}$", "next": "confirm"})
    return Scenario.model_validate(sample_dict)


def test_sensitive_values_are_never_stored(sample_dict: dict[str, Any]) -> None:
    scenario = sensitive_scenario(sample_dict)
    state, _ = walk(scenario, start(scenario), *HAPPY_PATH[:2])
    state, fb = apply(scenario, state, SessionEvent.typed("otp", "123456"))
    assert fb.code is FeedbackCode.OK and state.screen_id == "confirm"
    assert state.values == {"otp": DEFAULT_REDACTION}
    assert "123456" not in state.model_dump_json()


def test_storable_value_masks_never_ask_lookalikes(sample_dict: dict[str, Any]) -> None:
    scenario = sensitive_scenario(sample_dict)
    screen = scenario.screen("amount")
    assert screen is not None
    assert storable_value(scenario, screen, "amount", "200000") == "200000"
    assert storable_value(scenario, screen, "otp", "1") == DEFAULT_REDACTION
    assert storable_value(scenario, screen, "pin", "1") == DEFAULT_REDACTION
    assert storable_value(scenario, screen, "khong_co", "1") == DEFAULT_REDACTION


@pytest.mark.parametrize(
    ("actual", "expected", "result"),
    [
        (None, 1, False),
        ("200000", 200000, True),
        ("200.000", 200000, True),
        ("200,000", 200000, True),
        ("200000", 200001, False),
        ("abc", 200000, False),
        ("1.500", 1500, True),
        ("1,5", 15, True),
        ("true", True, True),
        ("1", True, True),
        ("0", False, True),
        ("yes", True, False),
        (" Nguyễn Văn A ", "nguyễn văn a", True),
        ("B", "A", False),
    ],
)
def test_value_matches(actual: str | None, expected: Any, result: bool) -> None:
    assert value_matches(actual, expected) is result


def test_succeeded_requires_success_screen(sample: Scenario) -> None:
    assert not succeeded(sample, "confirm", {"amount": "200000"})
    assert succeeded(sample, "done", {"amount": "200000"})
    assert not succeeded(sample, "done", {})


def test_generic_hint_respects_sentence_budget() -> None:
    one = Screen(id="s", title="S", coach_line="Bác bấm nút xanh nhé.")
    two = Screen(id="s", title="S", coach_line="Bác nhìn màn hình. Bác bấm nút xanh nhé.")
    assert generic_hint(one, WRONG_TAP_LEAD) == f"{WRONG_TAP_LEAD} {one.coach_line}"
    assert generic_hint(two, WRONG_TAP_LEAD) == two.coach_line


def test_highlight_of_empty_screen() -> None:
    assert highlight_of(Screen(id="s", title="S", coach_line="Xong.", terminal=True)) is None
