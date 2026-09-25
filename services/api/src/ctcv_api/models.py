"""SQLAlchemy 2.0 models for the nine tables of brief §4.

Only generic column types are used (``Uuid``, ``JSON``, ``DateTime(timezone=True)``,
``Enum(native_enum=False)``) so the same models run on SQLite in unit tests (D15)
and on PostgreSQL in production. Privacy rules (D28, brief §17.8):

* no CCCD / phone / e-mail / password / OTP column anywhere;
* ``users.display_name`` is a nickname or code issued by the volunteer (≤ 32 chars),
  never a legal name;
* ``classes.qr_token`` carries ``qr_token_expires_at`` and ``qr_token_revoked_at``;
* ``events.payload_json`` is validated against the per-type allowlist before every
  insert/update (:mod:`ctcv_api.events_schema`);
* ``qa_logs`` stores hashes of the question/answer, never the text.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Uuid,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates

from ctcv_api.enums import AccentPref, EventType, Role
from ctcv_api.events_schema import validate_payload

DISPLAY_NAME_MAX = 32
SLUG_MAX = 64
HASH_LEN = 64
TOKEN_MAX = 64
LEVEL_MIN, LEVEL_MAX = 1, 3


def utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(UTC)


def enum_column(enum_cls: type[StrEnum], name: str) -> Enum:
    """Portable enum type: VARCHAR + CHECK constraint instead of a native PostgreSQL enum."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        length=16,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID primary key generated client-side."""
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def timestamp(*, nullable: bool = False) -> Mapped[datetime]:
    """UTC timestamp column, defaulting to now unless nullable."""
    if nullable:
        return mapped_column(DateTime(timezone=True), nullable=True)
    return mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Base(DeclarativeBase):
    """Declarative base for every CTCV table."""


class User(Base):
    """A learner, volunteer or officer. Identity is a nickname/code, never PII."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"length(display_name) BETWEEN 1 AND {DISPLAY_NAME_MAX}",
            name="ck_users_display_name_len",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    role: Mapped[Role] = mapped_column(enum_column(Role, "role"), nullable=False)
    display_name: Mapped[str] = mapped_column(
        String(DISPLAY_NAME_MAX),
        nullable=False,
        comment="Nickname or code issued by the volunteer; never a legal name",
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("classes.id", use_alter=True, name="fk_users_class_id_classes"),
        nullable=True,
        index=True,
    )
    accent_pref: Mapped[AccentPref | None] = mapped_column(
        enum_column(AccentPref, "accent_pref"), nullable=True
    )
    consent_at: Mapped[datetime | None] = timestamp(nullable=True)
    created_at: Mapped[datetime] = timestamp()

    @validates("display_name")
    def _validate_display_name(self, _key: str, value: str) -> str:
        """Keep ``display_name`` a short volunteer-issued nickname/code."""
        cleaned = (value or "").strip()
        if not cleaned or len(cleaned) > DISPLAY_NAME_MAX:
            raise ValueError(
                f"display_name phải là biệt danh/mã 1–{DISPLAY_NAME_MAX} ký tự "
                "do tình nguyện viên cấp."
            )
        return cleaned


class Classroom(Base):
    """A class run by a volunteer; joined by scanning a revocable, expiring QR token."""

    __tablename__ = "classes"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ward_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    qr_token: Mapped[str] = mapped_column(String(TOKEN_MAX), nullable=False, unique=True)
    qr_token_expires_at: Mapped[datetime | None] = timestamp(nullable=True)
    qr_token_revoked_at: Mapped[datetime | None] = timestamp(nullable=True)
    created_at: Mapped[datetime] = timestamp()


class Scenario(Base):
    """A sandbox scenario loaded from ``sandbox/scenarios/*.json``."""

    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint(f"level BETWEEN {LEVEL_MIN} AND {LEVEL_MAX}", name="ck_scenarios_level"),
    )

    id: Mapped[str] = mapped_column(String(SLUG_MAX), primary_key=True)
    skill_group: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    checksum: Mapped[str] = mapped_column(String(HASH_LEN), nullable=False)


class Session(Base):
    """One practice run of a scenario; the source of every learning metric."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    scenario_id: Mapped[str] = mapped_column(
        String(SLUG_MAX), ForeignKey("scenarios.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = timestamp()
    ended_at: Mapped[datetime | None] = timestamp(nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mistakes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Event(Base):
    """A sandbox event; ``payload_json`` is restricted to the allowlist for ``type``."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id"), nullable=False, index=True
    )
    ts: Mapped[datetime] = timestamp()
    type: Mapped[EventType] = mapped_column(enum_column(EventType, "event_type"), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    @validates("payload_json")
    def _validate_payload(self, _key: str, value: Any) -> Any:
        """Reject payloads outside the allowlist as soon as ``type`` is known."""
        if self.type is not None:
            return validate_payload(self.type, value)
        return value


@event.listens_for(Event, "before_insert")
@event.listens_for(Event, "before_update")
def _enforce_payload_allowlist(_mapper: Any, _connection: Any, target: Event) -> None:
    """Final gate before any write: the payload must match the allowlist for ``type``."""
    validate_payload(target.type, target.payload_json)


class QaLog(Base):
    """A coach question/answer, stored as hashes only (no verbatim text)."""

    __tablename__ = "qa_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    question_hash: Mapped[str] = mapped_column(String(HASH_LEN), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(HASH_LEN), nullable=False)
    citations_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ts: Mapped[datetime] = timestamp()


class Drill(Base):
    """One scam-drill attempt; attempts 1 and 2 give the before/after score."""

    __tablename__ = "drills"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    scenario_key: Mapped[str] = mapped_column(String(SLUG_MAX), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_flags_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    ts: Mapped[datetime] = timestamp()


class ScreenJob(Base):
    """A screenshot-coaching job; the image itself lives in MinIO for 60 s only."""

    __tablename__ = "screen_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = timestamp()
    deleted_at: Mapped[datetime | None] = timestamp(nullable=True)
    boxes_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)


class AuditLog(Base):
    """Trace of volunteer/officer actions (``target`` is an id or path, never PII)."""

    __tablename__ = "audit"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(128), nullable=False)
    ts: Mapped[datetime] = timestamp()


TABLE_NAMES: tuple[str, ...] = tuple(sorted(Base.metadata.tables))
