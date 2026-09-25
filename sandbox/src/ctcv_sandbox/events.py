"""Session events sent by the client and their PII-free Redis Stream projection.

``SessionEvent`` mirrors the API contract (brief §3): ``type`` tap|input|back|ask,
optional ``target`` (element id) and ``value`` (typed text or spoken question).
``to_stream_record`` follows D28: the payload never carries the typed value — for
inputs only ``{target, valid, len}`` survive, and ``len`` is dropped for sensitive
elements; the question text of ``ask`` is never stored.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from ctcv_sandbox.schema import Ident

# Sanity bound on client-supplied text (typed values, spoken questions).
MAX_VALUE_CHARS = 500


class EventType(StrEnum):
    """Event kinds accepted by the engine."""

    TAP = "tap"
    INPUT = "input"
    BACK = "back"
    ASK = "ask"


def _now() -> datetime:
    return datetime.now(UTC)


class SessionEvent(BaseModel):
    """One client event inside a sandbox session."""

    model_config = ConfigDict(extra="forbid")

    type: EventType
    target: Ident | None = Field(default=None, description="Element id for tap/input.")
    value: str | None = Field(
        default=None, max_length=MAX_VALUE_CHARS, description="Typed text (input) or question."
    )
    ts: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _require_fields(self) -> SessionEvent:
        if self.type in (EventType.TAP, EventType.INPUT) and not self.target:
            raise PydanticCustomError(
                "event_target_missing",
                "Sự kiện {kind} phải có target.",
                {"kind": self.type.value},
            )
        if self.type is EventType.INPUT and self.value is None:
            raise PydanticCustomError("event_value_missing", "Sự kiện input phải có value.")
        return self

    @classmethod
    def tap(cls, target: str) -> SessionEvent:
        """Build a tap event."""
        return cls(type=EventType.TAP, target=target)

    @classmethod
    def typed(cls, target: str, value: str) -> SessionEvent:
        """Build an input event."""
        return cls(type=EventType.INPUT, target=target, value=value)

    @classmethod
    def back(cls) -> SessionEvent:
        """Build a back event."""
        return cls(type=EventType.BACK)

    @classmethod
    def ask(cls, question: str | None = None) -> SessionEvent:
        """Build an ask event (the question is never persisted)."""
        return cls(type=EventType.ASK, value=question)


def to_stream_record(
    event: SessionEvent, *, valid: bool | None = None, sensitive: bool = False
) -> dict[str, str]:
    """Project an event to a flat ``str → str`` mapping safe for a Redis Stream (no PII).

    Args:
        event: The client event.
        valid: For inputs, whether the value matched the action's pattern.
        sensitive: For inputs, whether the element is sensitive (drops ``len``).
    """
    record = {"type": event.type.value, "ts": event.ts.isoformat()}
    if event.target:
        record["target"] = event.target
    if event.type is EventType.INPUT:
        if valid is not None:
            record["valid"] = "1" if valid else "0"
        if not sensitive:
            record["len"] = str(len(event.value or ""))
    return record
