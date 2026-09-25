"""The nine tables of brief §4: names, required columns, privacy invariants, payload gate."""

from __future__ import annotations

import re
import uuid

import pytest
from sqlalchemy import JSON, DateTime, Enum, Uuid, inspect, text
from sqlalchemy.exc import IntegrityError

from ctcv_api import models
from ctcv_api.enums import AccentPref, EventType, Role
from ctcv_api.models import (
    DISPLAY_NAME_MAX,
    TABLE_NAMES,
    Base,
    Classroom,
    Event,
    Scenario,
    Session,
    User,
)
from ctcv_core.errors import ValidationFailed

REQUIRED_COLUMNS = {
    "users": {"id", "role", "display_name", "class_id", "accent_pref", "consent_at", "created_at"},
    "classes": {
        "id",
        "name",
        "ward_code",
        "volunteer_id",
        "qr_token",
        "qr_token_expires_at",
        "qr_token_revoked_at",
        "created_at",
    },
    "scenarios": {"id", "skill_group", "level", "spec_json", "version", "checksum"},
    "sessions": {
        "id",
        "user_id",
        "scenario_id",
        "started_at",
        "ended_at",
        "success",
        "steps",
        "mistakes",
        "hints_used",
        "duration_s",
    },
    "events": {"id", "session_id", "ts", "type", "payload_json"},
    "qa_logs": {
        "id",
        "user_id",
        "question_hash",
        "answer_hash",
        "citations_json",
        "confidence",
        "escalated",
        "ts",
    },
    "drills": {"id", "user_id", "scenario_key", "attempt", "score", "red_flags_json", "ts"},
    "screen_jobs": {"id", "user_id", "created_at", "deleted_at", "boxes_json"},
    "audit": {"id", "actor_id", "action", "target", "ts"},
}
PII_COLUMN_RE = re.compile(
    r"cccd|citizen_id|id_number|phone|dien_thoai|sdt|email|password|mat_khau|otp|card|so_the"
    r"|cvv|pin\b|address|dia_chi|full_name|ho_ten|birth|dob|national|question_text|answer_text",
    re.IGNORECASE,
)


def test_exactly_nine_tables():
    assert set(Base.metadata.tables) == set(REQUIRED_COLUMNS)
    assert len(TABLE_NAMES) == 9


@pytest.mark.parametrize("table", sorted(REQUIRED_COLUMNS))
def test_required_columns_present(table):
    columns = {column.name for column in Base.metadata.tables[table].columns}
    assert REQUIRED_COLUMNS[table] <= columns


def test_no_pii_columns_anywhere():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            assert not PII_COLUMN_RE.search(column.name), f"{table.name}.{column.name}"


def test_generic_column_types_for_sqlite_and_postgres():
    users = Base.metadata.tables["users"]
    assert isinstance(users.c.id.type, Uuid)
    assert isinstance(users.c.created_at.type, DateTime) and users.c.created_at.type.timezone
    assert isinstance(Base.metadata.tables["events"].c.payload_json.type, JSON)
    role_type = users.c.role.type
    assert isinstance(role_type, Enum) and role_type.native_enum is False
    assert set(role_type.enums) == {role.value for role in Role}


def test_enum_values_match_config_and_brief():
    assert [r.value for r in Role] == ["citizen", "volunteer", "officer"]
    assert [a.value for a in AccentPref] == ["bac", "trung", "nam"]
    assert [e.value for e in EventType] == ["tap", "input", "hint", "error", "ask"]


def test_display_name_is_documented_as_nickname():
    column = Base.metadata.tables["users"].c.display_name
    assert column.type.length == DISPLAY_NAME_MAX
    assert "never a legal name" in (column.comment or "")


@pytest.mark.parametrize("bad", ["", "   ", "x" * (DISPLAY_NAME_MAX + 1)])
def test_display_name_validator_rejects(bad):
    with pytest.raises(ValueError):
        User(role=Role.CITIZEN, display_name=bad)


def test_display_name_is_stripped():
    assert User(role=Role.CITIZEN, display_name="  HV01 ").display_name == "HV01"


def test_display_name_check_constraint_enforced_by_database(engine):
    too_long = "x" * (DISPLAY_NAME_MAX + 1)
    with engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO users (id, role, display_name, created_at) "
                "VALUES (:id, 'citizen', :name, CURRENT_TIMESTAMP)"
            ),
            {"id": uuid.uuid4().hex, "name": too_long},
        )


def test_qr_token_has_expiry_and_revocation(engine):
    columns = {c["name"]: c for c in inspect(engine).get_columns("classes")}
    assert columns["qr_token_expires_at"]["nullable"]
    assert columns["qr_token_revoked_at"]["nullable"]
    unique = {tuple(u["column_names"]) for u in inspect(engine).get_unique_constraints("classes")}
    assert ("qr_token",) in unique


def _seed(db_session) -> Session:
    volunteer = User(role=Role.VOLUNTEER, display_name="TNV01")
    citizen = User(role=Role.CITIZEN, display_name="HV01")
    scenario = Scenario(
        id="chuyen-khoan-qr",
        skill_group="thanh-toan-thue-so",
        level=1,
        spec_json={"id": "chuyen-khoan-qr"},
        version="1.0.0",
        checksum="0" * 64,
    )
    db_session.add_all([volunteer, citizen, scenario])
    db_session.flush()
    classroom = Classroom(name="Lớp 1", ward_code="79001", volunteer_id=volunteer.id, qr_token="t1")
    db_session.add(classroom)
    db_session.flush()
    citizen.class_id = classroom.id
    session = Session(user_id=citizen.id, scenario_id=scenario.id)
    db_session.add(session)
    db_session.flush()
    return session


def test_event_valid_payload_roundtrip(db_session):
    session = _seed(db_session)
    event = Event(
        session_id=session.id,
        type=EventType.TAP,
        payload_json={"element_id": "btn_qr", "screen_id": "home"},
    )
    db_session.add(event)
    db_session.commit()
    stored = db_session.get(Event, event.id)
    assert stored.payload_json == {"element_id": "btn_qr", "screen_id": "home"}
    assert stored.type is EventType.TAP


def test_event_with_free_text_key_is_rejected_before_insert(db_session):
    session = _seed(db_session)
    event = Event(session_id=session.id, type=EventType.ASK)
    with pytest.raises(ValidationFailed):
        event.payload_json = {
            "intent_class": "how-to",
            "question_hmac": "a" * 64,
            "text": "Tôi là A",
        }


def test_event_payload_gate_runs_at_flush_even_if_set_before_type(db_session):
    session = _seed(db_session)
    event = Event(payload_json={"free_text": "hello"})
    event.session_id = session.id
    event.type = EventType.HINT
    db_session.add(event)
    with pytest.raises(ValidationFailed):
        db_session.flush()
    db_session.rollback()


def test_event_payload_gate_runs_on_update(db_session):
    session = _seed(db_session)
    event = Event(session_id=session.id, type=EventType.ERROR, payload_json={"code": "WRONG_TAP"})
    db_session.add(event)
    db_session.commit()
    event.type = EventType.TAP
    with pytest.raises(ValidationFailed):
        db_session.commit()
    db_session.rollback()


def test_unique_qr_token(db_session):
    session = _seed(db_session)
    volunteer_id = db_session.get(Session, session.id).user_id
    db_session.add(
        Classroom(name="Lớp 2", ward_code="79001", volunteer_id=volunteer_id, qr_token="t1")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_utcnow_is_timezone_aware():
    assert models.utcnow().tzinfo is not None
