"""Pydantic v2 models for sandbox scenarios (E01 brief §5).

``config/schemas/scenario.schema.json`` is generated from :class:`Scenario` by
``scripts/gen_schemas.py``. Field-level rules (slug pattern, level range, the
"mô phỏng" label, the mandatory ``never_ask`` entries) live here; rules that need
the whole screen graph (reachability, terminal screens, banned terms) live in
:mod:`ctcv_sandbox.validator`.
"""

from __future__ import annotations

from enum import StrEnum
from functools import cached_property
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic_core import PydanticCustomError

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
IDENT_PATTERN = r"^[a-z][a-z0-9_]*$"
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
SIMULATION_MARK = "mô phỏng"
REQUIRED_NEVER_ASK: tuple[str, ...] = ("otp", "mat_khau")
MIN_LEVEL = 1
MAX_LEVEL = 3
MAX_TEXT_CHARS = 200

Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN, min_length=1, max_length=64)]
Ident = Annotated[str, StringConstraints(pattern=IDENT_PATTERN, min_length=1, max_length=40)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEXT_CHARS)]
Scalar = str | int | float | bool


class SkillGroup(StrEnum):
    """The five skill groups of the digital-literacy roadmap (idea §4, app.yaml)."""

    THIET_BI_CO_BAN = "thiet-bi-co-ban"
    DINH_DANH_VNEID = "dinh-danh-vneid"
    DICH_VU_CONG = "dich-vu-cong"
    THANH_TOAN_THUE_SO = "thanh-toan-thue-so"
    AN_TOAN_SO = "an-toan-so"


class ElementKind(StrEnum):
    """What a screen element renders as."""

    BUTTON = "button"
    INPUT = "input"
    TEXT = "text"
    BANNER = "banner"


class Colour(StrEnum):
    """Colours the coach can name out loud ("bấm nút màu xanh")."""

    XANH = "xanh"
    DO = "do"
    VANG = "vang"
    XAM = "xam"
    TRANG = "trang"


class _Strict(BaseModel):
    """Base model: unknown keys are rejected so the JSON Schema is closed."""

    model_config = ConfigDict(extra="forbid")


class Element(_Strict):
    """One visible element on a screen (button, input box, text or banner)."""

    id: Ident = Field(description="Unique within the screen; referenced by actions.")
    kind: ElementKind
    label: Text = Field(description="Text shown on the element (Vietnamese).")
    color: Colour | None = Field(default=None, description="Named colour, if any.")
    sensitive: bool = Field(
        default=False,
        description="True when the value must never be stored (OTP, password...).",
    )
    placeholder: Text | None = Field(default=None, description="Placeholder for inputs.")


class TapAction(_Strict):
    """Tapping ``tap`` moves to screen ``next``."""

    tap: Ident
    next: Ident


class InputAction(_Strict):
    """Typing a value matching ``value_pattern`` into ``input`` moves to ``next``."""

    input: Ident
    value_pattern: str = Field(default=r"^.+$", min_length=1, description="Python regex.")
    next: Ident


Action = TapAction | InputAction


class Mistake(_Strict):
    """A common wrong tap and the pre-written hint the coach says in response."""

    tap: Ident
    hint: Text = Field(description="At most two plain sentences, no jargon.")


class Screen(_Strict):
    """One screen of the simulated app."""

    id: Ident
    title: Text
    elements: list[Element] = Field(default_factory=list)
    valid_actions: list[Action] = Field(default_factory=list)
    common_mistakes: list[Mistake] = Field(default_factory=list)
    coach_line: Text = Field(description="What the coach says on arrival (at most 2 sentences).")
    terminal: bool = Field(default=False, description="True ends the session on arrival.")

    @cached_property
    def elements_by_id(self) -> dict[str, Element]:
        """Map element id → element (first occurrence wins; duplicates are a validator issue)."""
        mapping: dict[str, Element] = {}
        for element in self.elements:
            mapping.setdefault(element.id, element)
        return mapping

    def element(self, element_id: str) -> Element | None:
        """Return the element with ``element_id`` or ``None``."""
        return self.elements_by_id.get(element_id)


class Success(_Strict):
    """Session succeeds on reaching ``screen`` with every condition matching a value."""

    screen: Ident
    conditions: dict[str, Scalar] = Field(
        default_factory=dict,
        description="Expected values keyed by input element id.",
    )


class Scenario(_Strict):
    """A complete sandbox scenario (JSON state machine)."""

    id: Slug = Field(description="Slug, unique across sandbox/scenarios; equals the file stem.")
    skill_group: SkillGroup
    level: int = Field(ge=MIN_LEVEL, le=MAX_LEVEL)
    version: str = Field(pattern=VERSION_PATTERN)
    app_label: Text = Field(description='Must contain "mô phỏng" (simulated app label).')
    goal: Text
    intent_confirmation: Text = Field(description="First-turn question confirming intent.")
    start_screen: Ident
    screens: list[Screen] = Field(min_length=1)
    success: Success
    never_ask: list[Ident] = Field(min_length=1, description='Must include "otp" and "mat_khau".')
    fake_data: dict[str, Scalar] = Field(default_factory=dict)

    @field_validator("app_label")
    @classmethod
    def _app_label_is_simulated(cls, value: str) -> str:
        if SIMULATION_MARK not in value.casefold():
            raise PydanticCustomError(
                "app_label_not_simulated",
                'app_label phải chứa "Ứng dụng mô phỏng", nhận được: {label}',
                {"label": value},
            )
        return value

    @field_validator("never_ask")
    @classmethod
    def _never_ask_complete(cls, value: list[str]) -> list[str]:
        missing = [term for term in REQUIRED_NEVER_ASK if term not in value]
        if missing:
            raise PydanticCustomError(
                "never_ask_incomplete",
                "never_ask thiếu: {missing}",
                {"missing": ", ".join(missing)},
            )
        return value

    @cached_property
    def screens_by_id(self) -> dict[str, Screen]:
        """Map screen id → screen (first occurrence wins; duplicates are a validator issue)."""
        mapping: dict[str, Screen] = {}
        for screen in self.screens:
            mapping.setdefault(screen.id, screen)
        return mapping

    def screen(self, screen_id: str) -> Screen | None:
        """Return the screen with ``screen_id`` or ``None``."""
        return self.screens_by_id.get(screen_id)
