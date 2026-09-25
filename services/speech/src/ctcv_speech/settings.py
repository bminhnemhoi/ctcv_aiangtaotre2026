"""Runtime settings for the speech service.

Defaults come from ``config/models.yaml`` (``models.asr``, ``models.asr_small``,
``models.tts``) and ``config/app.yaml`` (``ports.speech``); the environment variables listed
in ``.env.example`` (``ASR_MODEL``, ``TTS_MODEL``, ``TTS_CACHE_DIR``, ``SPEECH_PORT``) plus
``TTS_MAX_TEXT_CHARS`` override them. Values that are blank or still read ``CHANGE_ME…`` are
treated as unset.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ctcv_core.config import load_config
from ctcv_core.errors import ValidationFailed

ASR_MODEL_ENV = "ASR_MODEL"
TTS_MODEL_ENV = "TTS_MODEL"
TTS_CACHE_DIR_ENV = "TTS_CACHE_DIR"
TTS_MAX_TEXT_CHARS_ENV = "TTS_MAX_TEXT_CHARS"
PORT_ENV = "SPEECH_PORT"
PLACEHOLDER_PREFIX = "CHANGE_ME"
UNDECIDED_PREFIX = "TBD"
DEFAULT_CACHE_DIRNAME = "ctcv-tts"
# Interim default for the longest text one TTS request may carry. A coach turn is at most
# `guardrails.max_sentences` (2) sentences plus "3 việc phải làm", so 1 000 characters is
# generous. E04 moves this into config/app.yaml (the config owner adds the key and its schema
# entry); until then TTS_MAX_TEXT_CHARS overrides it.
DEFAULT_TTS_MAX_TEXT_CHARS = 1000
MAX_PORT = 65535  # TCP port range upper bound (protocol constant, not a tunable threshold)
_DECIMAL_RE = re.compile(r"[0-9]+")


def default_tts_cache_dir() -> Path:
    """Return the fallback cache directory (``<tmp>/ctcv-tts``) used when the env is unset."""
    return Path(tempfile.gettempdir()) / DEFAULT_CACHE_DIRNAME


def env_or(env: Mapping[str, str], key: str, fallback: str) -> str:
    """Return ``env[key]`` unless it is missing, blank or a ``CHANGE_ME`` placeholder."""
    raw = env.get(key, "").strip()
    if not raw or raw.upper().startswith(PLACEHOLDER_PREFIX):
        return fallback
    return raw


def positive_int(raw: str, key: str, *, maximum: int | None = None) -> int:
    """Parse ``raw`` (ASCII digits only) as an integer in ``1..maximum``.

    Raises:
        ValidationFailed: with a Vietnamese message naming ``key`` when ``raw`` is not a plain
            decimal number (``1_000``, ``+5`` and non-ASCII digits are rejected) or is out of
            range.
    """
    if _DECIMAL_RE.fullmatch(raw) is None:
        raise ValidationFailed(
            f"Biến {key} phải là số nguyên dương (chữ số 0-9), nhận được: {raw!r}"
        )
    value = int(raw)
    if maximum is not None and not 1 <= value <= maximum:
        raise ValidationFailed(f"Biến {key} phải trong khoảng 1–{maximum}, nhận được: {value}")
    if value < 1:
        raise ValidationFailed(f"Biến {key} phải lớn hơn 0, nhận được: {value}")
    return value


def port_number(raw: str, key: str) -> int:
    """Parse a TCP port (``1..65535``) with ``positive_int``'s Vietnamese errors."""
    return positive_int(raw, key, maximum=MAX_PORT)


@dataclass(frozen=True, slots=True)
class SpeechSettings:
    """Immutable view of everything the speech service needs at start-up."""

    asr_model: str
    asr_small_model: str
    asr_served_by: str
    asr_confidence_threshold: float
    tts_model: str
    tts_served_by: str
    tts_cache_dir: Path
    tts_max_text_chars: int
    port: int

    @property
    def tts_decided(self) -> bool:
        """False while ``models.tts`` is still ``TBD-ADR-002`` (or a placeholder)."""
        return not self.tts_model.upper().startswith((UNDECIDED_PREFIX, PLACEHOLDER_PREFIX))

    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> SpeechSettings:
        """Build settings from the validated config files plus ``env`` (default: ``os.environ``)."""
        source = os.environ if env is None else env
        models = load_config("models")["models"]
        ports = load_config("app")["ports"]
        asr, tts = models["asr"], models["tts"]
        max_chars_raw = env_or(source, TTS_MAX_TEXT_CHARS_ENV, str(DEFAULT_TTS_MAX_TEXT_CHARS))
        return cls(
            asr_model=env_or(source, ASR_MODEL_ENV, str(asr["id"])),
            asr_small_model=str(models["asr_small"]["id"]),
            asr_served_by=str(asr["served_by"]),
            asr_confidence_threshold=float(asr["confidence_threshold"]),
            tts_model=env_or(source, TTS_MODEL_ENV, str(tts["id"])),
            tts_served_by=str(tts["served_by"]),
            tts_cache_dir=Path(env_or(source, TTS_CACHE_DIR_ENV, str(default_tts_cache_dir()))),
            tts_max_text_chars=positive_int(max_chars_raw, TTS_MAX_TEXT_CHARS_ENV),
            port=port_number(env_or(source, PORT_ENV, str(ports["speech"])), PORT_ENV),
        )
