"""Pydantic v2 models for scam drills (E01 brief §6 + D27).

``config/schemas/drill.schema.json`` is generated from :class:`Drill` by
``scripts/gen_schemas.py``. Field-level rules live here (enums, exactly one correct
option, three things, fixed label, ranges); content rules that need the D27 block
lists (URLs, phone numbers, real names, multi-turn markers, forbidden fields) live
in :mod:`ctcv_drills.validator`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic_core import PydanticCustomError

LABEL = "Đây là mô phỏng"
SIMULATION_TAG = "[Mô phỏng]"
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
MAX_TEXT_CHARS = 200
MIN_OPTIONS = 3
MAX_OPTIONS = 4
THREE_THINGS_COUNT = 3
MIN_VARIANT = 1
MAX_VARIANT = 5
MIN_SEVERITY = 1
MAX_SEVERITY = 3

Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN, min_length=1, max_length=64)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEXT_CHARS)]


class Channel(StrEnum):
    """How the simulated scammer reaches the learner."""

    SMS = "sms"
    ZALO = "zalo"
    CALL = "call"


class Impersonates(StrEnum):
    """Who the scammer pretends to be — a category label, never a real organisation."""

    CONG_AN = "cong-an"
    THUE = "thue"
    NGAN_HANG = "ngan-hang"
    SHIPPER = "shipper"
    TRUNG_THUONG = "trung-thuong"
    NGUOI_THAN = "nguoi-than"
    DIEN_LUC = "dien-luc"
    BUU_DIEN = "buu-dien"


class RedFlag(StrEnum):
    """Red-flag codes the debrief points at."""

    GIUC_CHUYEN_TIEN = "giuc-chuyen-tien"
    DOI_OTP = "doi-otp"
    XUNG_CO_QUAN = "xung-co-quan"
    LINK_LA = "link-la"
    DOA_DAM = "doa-dam"
    YEU_CAU_CAI_APP = "yeu-cau-cai-app"
    GIU_BI_MAT = "giu-bi-mat"
    TAI_KHOAN_LA = "tai-khoan-la"


class _Strict(BaseModel):
    """Base model: unknown keys are rejected so the JSON Schema is closed."""

    model_config = ConfigDict(extra="forbid")


class Option(_Strict):
    """One action the learner can choose."""

    id: Slug
    text: Text
    correct: bool


class Drill(_Strict):
    """One scam drill at behaviour-pattern level (a single labelled scammer turn)."""

    key: Slug = Field(description="Scenario key shared by all variants; equals the file stem.")
    channel: Channel
    impersonates: Impersonates
    variant: int = Field(ge=MIN_VARIANT, le=MAX_VARIANT)
    severity: int = Field(ge=MIN_SEVERITY, le=MAX_SEVERITY, description="Weight in scoring.")
    label: Literal["Đây là mô phỏng"] = Field(description="Fixed on-screen label.")
    pretext: Text = Field(description="One sentence describing the situation (≤ 30 words).")
    utterance: Text = Field(
        description='Exactly one turn the scammer says/sends, ≤ 40 words, contains "[Mô phỏng]".'
    )
    red_flags: list[RedFlag] = Field(min_length=1)
    options: list[Option] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    debrief: Text = Field(description="At most two plain sentences.")
    three_things: list[Text] = Field(min_length=THREE_THINGS_COUNT, max_length=THREE_THINGS_COUNT)

    @field_validator("red_flags")
    @classmethod
    def _red_flags_unique(cls, value: list[RedFlag]) -> list[RedFlag]:
        if len(set(value)) != len(value):
            raise PydanticCustomError("red_flag_duplicate", "red_flags có mã trùng nhau.")
        return value

    @field_validator("options")
    @classmethod
    def _options_well_formed(cls, value: list[Option]) -> list[Option]:
        ids = [option.id for option in value]
        if len(set(ids)) != len(ids):
            raise PydanticCustomError("option_id_duplicate", "options có id trùng nhau.")
        correct = sum(option.correct for option in value)
        if correct != 1:
            raise PydanticCustomError(
                "options_correct_count",
                "options phải có đúng một lựa chọn đúng, hiện có {count}.",
                {"count": correct},
            )
        return value

    def option(self, option_id: str) -> Option | None:
        """Return the option with ``option_id`` or ``None``."""
        return next((o for o in self.options if o.id == option_id), None)

    @property
    def correct_option(self) -> Option:
        """The single safe choice."""
        return next(o for o in self.options if o.correct)
