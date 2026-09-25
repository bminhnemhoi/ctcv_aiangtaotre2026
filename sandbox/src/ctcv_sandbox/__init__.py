"""ctcv-sandbox: scenario schema, validator and state-machine engine.

A scenario (``sandbox/scenarios/*.json``) is a small JSON state machine — screens,
elements, valid actions and common mistakes — that the web app renders under the
"Ứng dụng mô phỏng" label. :mod:`ctcv_sandbox.engine` walks it without calling any
model; :mod:`ctcv_sandbox.validator` rejects malformed scenarios before they ship.
"""

from ctcv_sandbox.engine import Feedback, FeedbackCode, State, apply, start
from ctcv_sandbox.events import EventType, SessionEvent, to_stream_record
from ctcv_sandbox.loader import checksum, list_scenarios, load_scenario
from ctcv_sandbox.schema import (
    Action,
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
from ctcv_sandbox.validator import Issue, validate, validate_data, validate_file

__all__ = [
    "Action",
    "Colour",
    "Element",
    "ElementKind",
    "EventType",
    "Feedback",
    "FeedbackCode",
    "InputAction",
    "Issue",
    "Mistake",
    "Scenario",
    "Screen",
    "SessionEvent",
    "SkillGroup",
    "State",
    "Success",
    "TapAction",
    "apply",
    "checksum",
    "list_scenarios",
    "load_scenario",
    "start",
    "to_stream_record",
    "validate",
    "validate_data",
    "validate_file",
]
