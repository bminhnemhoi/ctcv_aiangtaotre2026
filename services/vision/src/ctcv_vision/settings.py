"""Runtime settings for the vision service.

Defaults come from ``config/models.yaml`` (``models.ui_detector``, ``models.vlm``) and
``config/app.yaml`` (``screen_ttl_seconds``, ``ports.vision``); ``VLM_MODEL``,
``SCREEN_TTL_SECONDS`` and ``VISION_PORT`` from ``.env.example`` override them. Blank or
``CHANGE_ME`` values are treated as unset.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from ctcv_core.config import load_config
from ctcv_core.errors import ValidationFailed

VLM_MODEL_ENV = "VLM_MODEL"
SCREEN_TTL_ENV = "SCREEN_TTL_SECONDS"
PORT_ENV = "VISION_PORT"
PLACEHOLDER_PREFIX = "CHANGE_ME"


def env_or(env: Mapping[str, str], key: str, fallback: str) -> str:
    """Return ``env[key]`` unless it is missing, blank or a ``CHANGE_ME`` placeholder."""
    raw = env.get(key, "").strip()
    if not raw or raw.upper().startswith(PLACEHOLDER_PREFIX):
        return fallback
    return raw


def _positive_int(raw: str, key: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationFailed(f"Biến {key} phải là số nguyên, nhận được: {raw!r}") from exc
    if value <= 0:
        raise ValidationFailed(f"Biến {key} phải lớn hơn 0, nhận được: {value}")
    return value


@dataclass(frozen=True, slots=True)
class VisionSettings:
    """Immutable view of everything the vision service needs at start-up."""

    detector_model: str
    detector_served_by: str
    detector_confidence_threshold: float
    vlm_model: str
    vlm_confidence_threshold: float
    vlm_prompt: str
    screen_ttl_seconds: int
    port: int

    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> VisionSettings:
        """Build settings from the validated config files plus ``env`` (default: ``os.environ``)."""
        source = os.environ if env is None else env
        models = load_config("models")["models"]
        app = load_config("app")
        detector, vlm = models["ui_detector"], models["vlm"]
        ttl_raw = env_or(source, SCREEN_TTL_ENV, str(app["screen_ttl_seconds"]))
        port_raw = env_or(source, PORT_ENV, str(app["ports"]["vision"]))
        return cls(
            detector_model=str(detector["id"]),
            detector_served_by=str(detector["served_by"]),
            detector_confidence_threshold=float(detector["confidence_threshold"]),
            vlm_model=env_or(source, VLM_MODEL_ENV, str(vlm["id"])),
            vlm_confidence_threshold=float(vlm["confidence_threshold"]),
            vlm_prompt=str(vlm["prompt"]),
            screen_ttl_seconds=_positive_int(ttl_raw, SCREEN_TTL_ENV),
            port=_positive_int(port_raw, PORT_ENV),
        )
