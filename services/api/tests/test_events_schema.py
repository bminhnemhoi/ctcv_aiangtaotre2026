"""Allowlist of events.payload_json per type (brief D28)."""

from __future__ import annotations

import pytest

from ctcv_api.enums import EventType
from ctcv_api.events_schema import ALLOWED_KEYS, validate_payload
from ctcv_core.errors import ValidationFailed

VALID = {
    "tap": {"element_id": "btn_qr", "screen_id": "home"},
    "input": {"field_id": "amount", "valid": True, "len": 6},
    "hint": {"code": "H01"},
    "error": {"code": "WRONG_TAP"},
    "ask": {"intent_class": "how-to", "question_hmac": "a" * 64},
}


def test_allowlist_matches_brief():
    assert ALLOWED_KEYS == {
        "tap": {"element_id", "screen_id"},
        "input": {"field_id", "valid", "len"},
        "hint": {"code"},
        "error": {"code"},
        "ask": {"intent_class", "question_hmac"},
    }
    assert set(ALLOWED_KEYS) == {e.value for e in EventType}


@pytest.mark.parametrize("event_type", sorted(VALID))
def test_valid_payload_is_returned_canonically(event_type):
    assert validate_payload(event_type, VALID[event_type]) == VALID[event_type]
    assert validate_payload(EventType(event_type), dict(VALID[event_type])) == VALID[event_type]


@pytest.mark.parametrize("event_type", sorted(VALID))
@pytest.mark.parametrize("free_key", ["text", "value", "question", "note", "display_name"])
def test_free_text_keys_are_rejected(event_type, free_key):
    payload = {**VALID[event_type], free_key: "Tôi tên Nguyễn Văn A, số 0912345678"}
    with pytest.raises(ValidationFailed) as info:
        validate_payload(event_type, payload)
    assert info.value.code == "EVENT_PAYLOAD_INVALID"
    assert info.value.status == 422
    assert info.value.details["allowed"] == sorted(ALLOWED_KEYS[event_type])
    assert free_key in {loc for err in info.value.details["errors"] for loc in err["loc"]}


@pytest.mark.parametrize("event_type", sorted(VALID))
def test_missing_key_is_rejected(event_type):
    payload = dict(VALID[event_type])
    payload.pop(next(iter(payload)))
    with pytest.raises(ValidationFailed):
        validate_payload(event_type, payload)


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        ("input", {"field_id": "amount", "valid": "yes", "len": 6}),
        ("input", {"field_id": "amount", "valid": True, "len": "6"}),
        ("input", {"field_id": "amount", "valid": True, "len": -1}),
        ("tap", {"element_id": "Bấm vào đây", "screen_id": "home"}),
        ("ask", {"intent_class": "how-to", "question_hmac": "not-hex"}),
        ("hint", {"code": "mã có dấu cách"}),
    ],
)
def test_wrong_types_and_shapes_are_rejected(event_type, payload):
    with pytest.raises(ValidationFailed) as info:
        validate_payload(event_type, payload)
    assert info.value.code == "EVENT_PAYLOAD_INVALID"


@pytest.mark.parametrize("event_type", ["back", "swipe", "", "TAP"])
def test_unknown_event_type_is_rejected(event_type):
    with pytest.raises(ValidationFailed) as info:
        validate_payload(event_type, {})
    assert info.value.code == "EVENT_TYPE_INVALID"
    assert info.value.details["allowed"] == ["tap", "input", "hint", "error", "ask"]


@pytest.mark.parametrize("payload", [None, "text", ["a"], 1])
def test_non_object_payload_is_rejected(payload):
    with pytest.raises(ValidationFailed) as info:
        validate_payload("tap", payload)
    assert info.value.code == "EVENT_PAYLOAD_INVALID"


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        ("tap", {"element_id": "012345678901", "screen_id": "home"}),
        ("hint", {"code": "0912345678"}),
        ("input", {"field_id": "4111-1111-1111-1111", "valid": True, "len": 1}),
    ],
)
def test_pii_looking_values_are_rejected(event_type, payload):
    with pytest.raises(ValidationFailed) as info:
        validate_payload(event_type, payload)
    assert info.value.code == "EVENT_PAYLOAD_PII"
    assert set(info.value.details) == {"type", "field"}
