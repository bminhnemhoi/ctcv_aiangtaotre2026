from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ctcv_sandbox.events import MAX_VALUE_CHARS, EventType, SessionEvent, to_stream_record


def test_builders() -> None:
    assert SessionEvent.tap("btn").type is EventType.TAP
    assert SessionEvent.typed("amount", "1").value == "1"
    assert SessionEvent.back().target is None
    assert SessionEvent.ask().value is None
    assert SessionEvent.ask("Bấm đâu?").value == "Bấm đâu?"


def test_timestamp_is_utc_aware() -> None:
    ts = SessionEvent.back().ts
    assert ts.tzinfo is not None and ts.utcoffset() is not None
    assert abs((datetime.now(UTC) - ts).total_seconds()) < 5


@pytest.mark.parametrize("payload", [{"type": "tap"}, {"type": "input", "value": "x"}])
def test_tap_and_input_need_target(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError) as exc:
        SessionEvent.model_validate(payload)
    assert exc.value.errors()[0]["type"] == "event_target_missing"


def test_input_needs_value() -> None:
    with pytest.raises(ValidationError) as exc:
        SessionEvent.model_validate({"type": "input", "target": "amount"})
    assert exc.value.errors()[0]["type"] == "event_value_missing"


def test_value_length_and_target_pattern() -> None:
    with pytest.raises(ValidationError):
        SessionEvent.ask("x" * (MAX_VALUE_CHARS + 1))
    with pytest.raises(ValidationError):
        SessionEvent.tap("Btn-Xau")
    with pytest.raises(ValidationError):
        SessionEvent.model_validate({"type": "swipe"})


def test_stream_record_for_input_has_no_value() -> None:
    event = SessionEvent.typed("amount", "200000")
    record = to_stream_record(event, valid=True)
    assert record == {
        "type": "input",
        "ts": event.ts.isoformat(),
        "target": "amount",
        "valid": "1",
        "len": "6",
    }
    assert to_stream_record(event, valid=False)["valid"] == "0"
    assert "valid" not in to_stream_record(event)


def test_stream_record_for_sensitive_input_drops_length() -> None:
    event = SessionEvent.typed("otp", "123456")
    record = to_stream_record(event, valid=True, sensitive=True)
    assert record == {"type": "input", "ts": event.ts.isoformat(), "target": "otp", "valid": "1"}
    assert "123456" not in "".join(record.values())


def test_stream_record_for_ask_never_keeps_question() -> None:
    event = SessionEvent.ask("Số căn cước của tôi là 0123 4567 8901 đúng không?")
    record = to_stream_record(event)
    assert record == {"type": "ask", "ts": event.ts.isoformat()}


def test_stream_record_values_are_strings() -> None:
    for event in (SessionEvent.tap("btn"), SessionEvent.back(), SessionEvent.typed("a", "b")):
        record = to_stream_record(event, valid=True)
        assert all(isinstance(v, str) for v in record.values())
        assert "value" not in record
