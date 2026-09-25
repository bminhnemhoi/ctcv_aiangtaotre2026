"""Allowlisted shapes of ``events.payload_json`` per event type (brief D28, §17.8).

Only these keys may ever be stored:

* ``tap``   → ``{element_id, screen_id}``
* ``input`` → ``{field_id, valid, len}`` (never the typed value)
* ``hint``  → ``{code}``
* ``error`` → ``{code}``
* ``ask``   → ``{intent_class, question_hmac}`` (never the question text)

:func:`validate_payload` is called by the ORM before every insert/update of an
event; free-text keys, wrong types and PII-looking values are rejected with a
422 ``ValidationFailed`` carrying a Vietnamese message.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ctcv_api.enums import EventType
from ctcv_core.errors import ValidationFailed
from ctcv_core.logging import PiiPatterns, load_pii_patterns, scrub_pii

SLUG_PATTERN = r"^[a-z0-9_-]{1,64}$"
CODE_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
HMAC_PATTERN = r"^[0-9a-f]{64}$"
MAX_INPUT_LEN = 10_000


class _StrictPayload(BaseModel):
    """Base for payload models: unknown keys are an error, no type coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


class TapPayload(_StrictPayload):
    """A tap on a sandbox element."""

    element_id: str = Field(pattern=SLUG_PATTERN, description="Mã phần tử được bấm")
    screen_id: str = Field(pattern=SLUG_PATTERN, description="Mã màn hình lúc bấm")


class InputPayload(_StrictPayload):
    """Text entered into a sandbox field — only validity and length are kept."""

    field_id: str = Field(pattern=SLUG_PATTERN, description="Mã ô nhập")
    valid: bool = Field(description="Giá trị nhập có khớp mẫu không")
    len: int = Field(ge=0, le=MAX_INPUT_LEN, description="Độ dài chuỗi đã nhập")


class HintPayload(_StrictPayload):
    """A hint shown by the coach."""

    code: str = Field(pattern=CODE_PATTERN, description="Mã gợi ý")


class ErrorPayload(_StrictPayload):
    """A mistake made by the learner."""

    code: str = Field(pattern=CODE_PATTERN, description="Mã lỗi thao tác")


class AskPayload(_StrictPayload):
    """A question asked to the coach — stored as intent class + HMAC only."""

    intent_class: str = Field(pattern=SLUG_PATTERN, description="Nhóm ý định của câu hỏi")
    question_hmac: str = Field(pattern=HMAC_PATTERN, description="HMAC-SHA256 của câu hỏi (hex)")


PAYLOAD_MODELS: dict[EventType, type[_StrictPayload]] = {
    EventType.TAP: TapPayload,
    EventType.INPUT: InputPayload,
    EventType.HINT: HintPayload,
    EventType.ERROR: ErrorPayload,
    EventType.ASK: AskPayload,
}

ALLOWED_KEYS: dict[str, frozenset[str]] = {
    etype.value: frozenset(model.model_fields) for etype, model in PAYLOAD_MODELS.items()
}


@cache
def _pii_patterns() -> PiiPatterns:
    return load_pii_patterns()


def _reject_pii(data: dict[str, Any], etype: EventType) -> None:
    """Raise when any string value changes under the guardrail PII regexes."""
    for key, value in data.items():
        if isinstance(value, str) and scrub_pii(value, _pii_patterns()) != value:
            raise ValidationFailed(
                "Nội dung sự kiện chứa thông tin cá nhân nên không được lưu.",
                code="EVENT_PAYLOAD_PII",
                details={"type": etype.value, "field": key},
            )


def _coerce_type(event_type: str | EventType) -> EventType:
    try:
        return EventType(event_type)
    except ValueError as exc:
        raise ValidationFailed(
            "Loại sự kiện không hợp lệ.",
            code="EVENT_TYPE_INVALID",
            details={"type": str(event_type), "allowed": [e.value for e in EventType]},
        ) from exc


def validate_payload(event_type: str | EventType, payload: Any) -> dict[str, Any]:
    """Return the canonical payload for ``event_type`` or raise ``ValidationFailed`` (422).

    Unknown event types, non-object payloads, extra/free-text keys, wrong value types
    and PII-looking strings are all rejected before anything reaches the database.
    """
    etype = _coerce_type(event_type)
    if not isinstance(payload, dict):
        raise ValidationFailed(
            "Nội dung sự kiện phải là một bảng khóa–giá trị.",
            code="EVENT_PAYLOAD_INVALID",
            details={"type": etype.value, "allowed": sorted(ALLOWED_KEYS[etype.value])},
        )
    try:
        model = PAYLOAD_MODELS[etype].model_validate(payload)
    except ValidationError as exc:
        raise ValidationFailed(
            "Nội dung sự kiện có trường không được phép hoặc sai kiểu.",
            code="EVENT_PAYLOAD_INVALID",
            details={
                "type": etype.value,
                "allowed": sorted(ALLOWED_KEYS[etype.value]),
                "errors": [
                    {"loc": [str(p) for p in err["loc"]], "type": err["type"]}
                    for err in exc.errors()
                ],
            },
        ) from exc
    data = model.model_dump()
    _reject_pii(data, etype)
    return data
