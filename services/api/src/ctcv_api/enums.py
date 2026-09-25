"""Closed vocabularies shared by models, schemas and auth.

The values mirror ``config/app.yaml`` (``roles``) and brief §4; a test asserts they
stay in sync so the config file remains the single source of truth.
"""

from enum import StrEnum


class Role(StrEnum):
    """The three user roles (idea §9): citizen, volunteer, officer."""

    CITIZEN = "citizen"
    VOLUNTEER = "volunteer"
    OFFICER = "officer"


class AccentPref(StrEnum):
    """Preferred regional accent for TTS/ASR (``users.accent_pref``)."""

    BAC = "bac"
    TRUNG = "trung"
    NAM = "nam"


class EventType(StrEnum):
    """Stored sandbox event types (``events.type``)."""

    TAP = "tap"
    INPUT = "input"
    HINT = "hint"
    ERROR = "error"
    ASK = "ask"
