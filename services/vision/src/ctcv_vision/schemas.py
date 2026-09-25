"""Request/response models of the vision service (brief §3 ``ScreenOut``, §4 ``boxes_json``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Box(BaseModel):
    """One detected element or masked region — ``{cls, x, y, w, h}``, never any text."""

    model_config = ConfigDict(extra="forbid")

    cls: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=1)
    h: int = Field(ge=1)


class DetectOut(BaseModel):
    """Boxes found by the UI detector on one screenshot."""

    boxes: list[Box]
    model: str


class ScreenOut(BaseModel):
    """What the coach needs from a screenshot: state, one next step, highlight boxes."""

    screen_state: str
    step_text: str
    boxes: list[Box]


class HealthOut(BaseModel):
    """Health payload shared by every CTCV service: ``{status, version, checks}``."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    checks: dict[str, str]
    models: dict[str, str]
    screen_ttl_seconds: int
