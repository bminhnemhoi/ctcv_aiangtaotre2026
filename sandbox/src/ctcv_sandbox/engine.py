"""Deterministic state machine that walks a scenario without calling any model.

``start(scenario)`` creates a :class:`State`; ``apply(scenario, state, event)`` returns
a new state plus :class:`Feedback` (what the coach says, whether it was a mistake,
whether the session is done). States are immutable snapshots — ``apply`` never
mutates its input — so they can be stored per session and replayed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ctcv_core.errors import ValidationFailed
from ctcv_core.logging import DEFAULT_REDACTION
from ctcv_core.text import count_sentences
from ctcv_sandbox.events import EventType, SessionEvent
from ctcv_sandbox.schema import InputAction, Scalar, Scenario, Screen, TapAction
from ctcv_sandbox.validator import load_rules, looks_sensitive

# Short Vietnamese lead-ins for generic hints (the screen's coach_line is appended).
WRONG_TAP_LEAD = "Chưa đúng nút đó bác ạ."
INVALID_INPUT_LEAD = "Bác nhập chưa đúng rồi."
SCENARIO_INVALID = "SCENARIO_INVALID"
SCREEN_MISSING_MESSAGE = "Bài học này đang lỗi, bác thử chọn bài khác nhé."
_NUMBER_SEPARATORS_RE = re.compile(r"[\s.,]")


class FeedbackCode(StrEnum):
    """Why the engine answered the way it did (machine-readable)."""

    OK = "ok"
    DONE = "done"
    ALREADY_DONE = "already_done"
    KNOWN_MISTAKE = "known_mistake"
    WRONG_ELEMENT = "wrong_element"
    UNKNOWN_ELEMENT = "unknown_element"
    INVALID_INPUT = "invalid_input"
    BACK = "back"
    ASK = "ask"


class State(BaseModel):
    """Snapshot of one sandbox session."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    screen_id: str
    values: dict[str, str] = Field(default_factory=dict)
    steps: int = 0
    mistakes: int = 0
    hints_used: int = 0
    done: bool = False
    success: bool = False
    history: list[str] = Field(default_factory=list, description="Previous screens (for back).")


class Feedback(BaseModel):
    """What to say and show after an event."""

    model_config = ConfigDict(extra="forbid")

    code: FeedbackCode
    say: str = Field(description="Line the coach speaks next (≤ 2 sentences).")
    hint: str | None = Field(default=None, description="Set only when ``mistake`` is true.")
    mistake: bool = False
    done: bool = False
    highlight: str | None = Field(default=None, description="Element id to highlight next.")


def start(scenario: Scenario) -> State:
    """Create the initial state on ``scenario.start_screen``."""
    screen = _screen(scenario, scenario.start_screen)
    return State(scenario_id=scenario.id, screen_id=screen.id)


def apply(scenario: Scenario, state: State, event: SessionEvent) -> tuple[State, Feedback]:
    """Apply one event and return ``(new_state, feedback)``."""
    screen = _screen(scenario, state.screen_id)
    if state.done:
        return state, Feedback(code=FeedbackCode.ALREADY_DONE, say=screen.coach_line, done=True)
    return _HANDLERS[event.type](scenario, state, screen, event)


def _screen(scenario: Scenario, screen_id: str) -> Screen:
    screen = scenario.screen(screen_id)
    if screen is None:
        raise ValidationFailed(
            SCREEN_MISSING_MESSAGE,
            code=SCENARIO_INVALID,
            details={"scenario_id": scenario.id, "screen_id": screen_id},
        )
    return screen


def highlight_of(screen: Screen) -> str | None:
    """Element id of the first valid action on ``screen`` (what the UI should highlight)."""
    for action in screen.valid_actions:
        return action.tap if isinstance(action, TapAction) else action.input
    return None


def generic_hint(screen: Screen, lead: str) -> str:
    """Lead-in plus the screen's coach line, kept within ``guardrails.max_sentences``."""
    if count_sentences(screen.coach_line) < load_rules().max_sentences:
        return f"{lead} {screen.coach_line}"
    return screen.coach_line


def _advance(scenario: Scenario, state: State, next_id: str) -> tuple[State, Feedback]:
    nxt = _screen(scenario, next_id)
    done = nxt.terminal
    new_state = state.model_copy(
        update={
            "screen_id": nxt.id,
            "steps": state.steps + 1,
            "history": [*state.history, state.screen_id],
            "done": done,
            "success": done and succeeded(scenario, nxt.id, state.values),
        }
    )
    feedback = Feedback(
        code=FeedbackCode.DONE if done else FeedbackCode.OK,
        say=nxt.coach_line,
        done=done,
        highlight=None if done else highlight_of(nxt),
    )
    return new_state, feedback


def _mistake(state: State, screen: Screen, hint: str, code: FeedbackCode) -> tuple[State, Feedback]:
    new_state = state.model_copy(
        update={
            "steps": state.steps + 1,
            "mistakes": state.mistakes + 1,
            "hints_used": state.hints_used + 1,
        }
    )
    feedback = Feedback(
        code=code, say=hint, hint=hint, mistake=True, highlight=highlight_of(screen)
    )
    return new_state, feedback


def _unknown_code(screen: Screen, target: str | None) -> FeedbackCode:
    if target and screen.element(target) is not None:
        return FeedbackCode.WRONG_ELEMENT
    return FeedbackCode.UNKNOWN_ELEMENT


def _apply_tap(
    scenario: Scenario, state: State, screen: Screen, event: SessionEvent
) -> tuple[State, Feedback]:
    for action in screen.valid_actions:
        if isinstance(action, TapAction) and action.tap == event.target:
            return _advance(scenario, state, action.next)
    for mistake in screen.common_mistakes:
        if mistake.tap == event.target:
            return _mistake(state, screen, mistake.hint, FeedbackCode.KNOWN_MISTAKE)
    hint = generic_hint(screen, WRONG_TAP_LEAD)
    return _mistake(state, screen, hint, _unknown_code(screen, event.target))


def _apply_input(
    scenario: Scenario, state: State, screen: Screen, event: SessionEvent
) -> tuple[State, Feedback]:
    action = next(
        (a for a in screen.valid_actions if isinstance(a, InputAction) and a.input == event.target),
        None,
    )
    if action is None:
        hint = generic_hint(screen, WRONG_TAP_LEAD)
        return _mistake(state, screen, hint, _unknown_code(screen, event.target))
    value = event.value or ""
    if re.fullmatch(action.value_pattern, value) is None:
        hint = generic_hint(screen, INVALID_INPUT_LEAD)
        return _mistake(state, screen, hint, FeedbackCode.INVALID_INPUT)
    stored = storable_value(scenario, screen, action.input, value)
    with_value = state.model_copy(update={"values": {**state.values, action.input: stored}})
    return _advance(scenario, with_value, action.next)


def _apply_back(
    scenario: Scenario, state: State, screen: Screen, event: SessionEvent
) -> tuple[State, Feedback]:
    if not state.history:
        say = screen.coach_line
        return state, Feedback(code=FeedbackCode.BACK, say=say, highlight=highlight_of(screen))
    previous = _screen(scenario, state.history[-1])
    new_state = state.model_copy(
        update={
            "screen_id": previous.id,
            "history": state.history[:-1],
            "steps": state.steps + 1,
        }
    )
    feedback = Feedback(
        code=FeedbackCode.BACK, say=previous.coach_line, highlight=highlight_of(previous)
    )
    return new_state, feedback


def _apply_ask(
    scenario: Scenario, state: State, screen: Screen, event: SessionEvent
) -> tuple[State, Feedback]:
    new_state = state.model_copy(update={"hints_used": state.hints_used + 1})
    feedback = Feedback(
        code=FeedbackCode.ASK,
        say=screen.coach_line,
        hint=screen.coach_line,
        highlight=highlight_of(screen),
    )
    return new_state, feedback


_Handler = Callable[[Scenario, State, Screen, SessionEvent], tuple[State, Feedback]]
_HANDLERS: dict[EventType, _Handler] = {
    EventType.TAP: _apply_tap,
    EventType.INPUT: _apply_input,
    EventType.BACK: _apply_back,
    EventType.ASK: _apply_ask,
}


def storable_value(scenario: Scenario, screen: Screen, element_id: str, value: str) -> str:
    """Return ``value`` unless the element is sensitive or matches ``never_ask`` (then a mask)."""
    element = screen.element(element_id)
    if element is None:
        return DEFAULT_REDACTION
    if element.sensitive or looks_sensitive(element, scenario.never_ask):
        return DEFAULT_REDACTION
    return value


def value_matches(actual: str | None, expected: Scalar) -> bool:
    """Compare a typed value with a success condition (numbers ignore ``.``/``,`` separators)."""
    if actual is None:
        return False
    if isinstance(expected, bool):
        return actual.strip().casefold() in {str(expected).casefold(), "1" if expected else "0"}
    if isinstance(expected, int | float):
        try:
            return float(_NUMBER_SEPARATORS_RE.sub("", actual)) == float(expected)
        except ValueError:
            return False
    return actual.strip().casefold() == expected.strip().casefold()


def succeeded(scenario: Scenario, screen_id: str, values: Mapping[str, str]) -> bool:
    """True when ``screen_id`` is the success screen and every condition holds."""
    if screen_id != scenario.success.screen:
        return False
    conditions = scenario.success.conditions
    return all(value_matches(values.get(key), expected) for key, expected in conditions.items())
