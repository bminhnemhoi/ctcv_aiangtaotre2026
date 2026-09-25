"""Request/response models of the speech service (brief §3: ``AsrOut``, ``TtsIn``, ``TtsOut``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AccentTag = Literal["bac", "trung", "nam", "unknown"]


class AsrOut(BaseModel):
    """Transcription result."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    accent_tag: AccentTag = "unknown"


class TtsIn(BaseModel):
    """Text to speak; ``voice`` selects a cached voice (default voice when omitted).

    Unknown fields are rejected (a client must never be able to smuggle extra data such as
    an OTP into a speech request). ``text`` is stripped and must not be blank; its maximum
    length is enforced by the route from ``SpeechSettings.tts_max_text_chars``.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    voice: str | None = None

    @field_validator("text")
    @classmethod
    def _strip_and_require_text(cls, value: str) -> str:
        """Strip surrounding whitespace and reject text that is blank once stripped."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Văn bản cần đọc đang trống, bác nhập lại giúp cháu nhé.")
        return stripped

    @field_validator("voice")
    @classmethod
    def _blank_voice_means_default(cls, value: str | None) -> str | None:
        """Treat a blank voice name as "not given" so the default voice is used."""
        if value is None:
            return None
        return value.strip() or None


class TtsOut(BaseModel):
    """Where the audio clip can be fetched and whether it came from the cache."""

    audio_url: str
    cached: bool


class HealthOut(BaseModel):
    """Health payload shared by every CTCV service: ``{status, version, checks}``."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    checks: dict[str, str]
    models: dict[str, str]
