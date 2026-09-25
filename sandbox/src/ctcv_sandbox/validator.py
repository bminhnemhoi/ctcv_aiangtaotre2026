"""Structural validation of sandbox scenarios (E01 brief §5).

:func:`validate` takes a parsed :class:`~ctcv_sandbox.schema.Scenario` and returns a
list of :class:`Issue` (empty = valid). :func:`validate_data` and
:func:`validate_file` additionally turn schema errors (Pydantic) into issues so the
CLI and CI get one uniform report. Every issue carries a stable machine ``code``
(see :class:`Code`) and a Vietnamese ``message``.

Style limits come from ``config/guardrails.yaml`` (``max_sentences``,
``banned_terms``); nothing here is hard-coded.
"""

from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ctcv_core.config import load_config
from ctcv_core.text import contains_banned_terms, count_sentences
from ctcv_sandbox.normalize import ascii_slug, contains_token
from ctcv_sandbox.schema import (
    Element,
    ElementKind,
    InputAction,
    Scenario,
    Screen,
    TapAction,
)


class Code(StrEnum):
    """Machine codes for every rule a scenario can break."""

    # --- schema level (from Pydantic) ---
    SCHEMA_INVALID = "SCHEMA_INVALID"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    FIELD_MISSING = "FIELD_MISSING"
    ENUM_INVALID = "ENUM_INVALID"
    STRING_TOO_LONG = "STRING_TOO_LONG"
    IDENT_INVALID = "IDENT_INVALID"
    SLUG_INVALID = "SLUG_INVALID"
    LEVEL_OUT_OF_RANGE = "LEVEL_OUT_OF_RANGE"
    VERSION_INVALID = "VERSION_INVALID"
    SCREENS_EMPTY = "SCREENS_EMPTY"
    APP_LABEL_NOT_SIMULATED = "APP_LABEL_NOT_SIMULATED"
    NEVER_ASK_INCOMPLETE = "NEVER_ASK_INCOMPLETE"
    # --- file level ---
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    JSON_INVALID = "JSON_INVALID"
    NOT_AN_OBJECT = "NOT_AN_OBJECT"
    ID_FILENAME_MISMATCH = "ID_FILENAME_MISMATCH"
    DUPLICATE_SCENARIO_ID = "DUPLICATE_SCENARIO_ID"
    # --- graph level ---
    DUPLICATE_SCREEN_ID = "DUPLICATE_SCREEN_ID"
    DUPLICATE_ELEMENT_ID = "DUPLICATE_ELEMENT_ID"
    START_SCREEN_MISSING = "START_SCREEN_MISSING"
    SCREEN_DEAD_END = "SCREEN_DEAD_END"
    ACTION_ELEMENT_MISSING = "ACTION_ELEMENT_MISSING"
    ACTION_KIND_MISMATCH = "ACTION_KIND_MISMATCH"
    ACTION_SCREEN_MISSING = "ACTION_SCREEN_MISSING"
    INPUT_PATTERN_INVALID = "INPUT_PATTERN_INVALID"
    MISTAKE_ELEMENT_MISSING = "MISTAKE_ELEMENT_MISSING"
    SCREEN_UNREACHABLE = "SCREEN_UNREACHABLE"
    SCREEN_NO_EXIT = "SCREEN_NO_EXIT"
    NO_TERMINAL_SCREEN = "NO_TERMINAL_SCREEN"
    SUCCESS_SCREEN_MISSING = "SUCCESS_SCREEN_MISSING"
    SUCCESS_SCREEN_NOT_TERMINAL = "SUCCESS_SCREEN_NOT_TERMINAL"
    SUCCESS_CONDITION_UNKNOWN_FIELD = "SUCCESS_CONDITION_UNKNOWN_FIELD"
    COACH_LINE_TOO_LONG = "COACH_LINE_TOO_LONG"
    COACH_LINE_BANNED_TERM = "COACH_LINE_BANNED_TERM"
    HINT_TOO_LONG = "HINT_TOO_LONG"
    HINT_BANNED_TERM = "HINT_BANNED_TERM"
    SENSITIVE_INPUT_UNFLAGGED = "SENSITIVE_INPUT_UNFLAGGED"


class Issue(BaseModel):
    """One validation problem: machine ``code``, Vietnamese ``message``, JSON ``path``."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    path: str = ""

    def __str__(self) -> str:
        """Render as ``[CODE] path: message``."""
        location = f" {self.path}:" if self.path else ""
        return f"[{self.code}]{location} {self.message}"


class Rules(BaseModel):
    """Style limits read from ``config/guardrails.yaml``."""

    max_sentences: int
    banned_terms: list[str | dict[str, str]]


def load_rules() -> Rules:
    """Read ``max_sentences`` and ``banned_terms`` from ``config/guardrails.yaml``."""
    cfg = load_config("guardrails")
    return Rules(max_sentences=cfg["max_sentences"], banned_terms=cfg["banned_terms"])


# ----------------------------------------------------------------------------- schema errors

_CUSTOM_CODES: dict[str, Code] = {
    "app_label_not_simulated": Code.APP_LABEL_NOT_SIMULATED,
    "never_ask_incomplete": Code.NEVER_ASK_INCOMPLETE,
}
_TOP_LEVEL_CODES: dict[tuple[str, str], Code] = {
    ("id", "string_pattern_mismatch"): Code.SLUG_INVALID,
    ("level", "greater_than_equal"): Code.LEVEL_OUT_OF_RANGE,
    ("level", "less_than_equal"): Code.LEVEL_OUT_OF_RANGE,
    ("version", "string_pattern_mismatch"): Code.VERSION_INVALID,
    ("screens", "too_short"): Code.SCREENS_EMPTY,
    ("never_ask", "too_short"): Code.NEVER_ASK_INCOMPLETE,
}
_TYPE_CODES: dict[str, Code] = {
    "extra_forbidden": Code.UNKNOWN_FIELD,
    "missing": Code.FIELD_MISSING,
    "enum": Code.ENUM_INVALID,
    "string_too_long": Code.STRING_TOO_LONG,
    "string_pattern_mismatch": Code.IDENT_INVALID,
}


def join_loc(loc: Iterable[Any]) -> str:
    """Render a Pydantic ``loc`` tuple as ``screens[0].elements[1].id``."""
    parts: list[str] = []
    for part in loc:
        parts.append(f"[{part}]" if isinstance(part, int) else (f".{part}" if parts else str(part)))
    return "".join(parts)


def issues_from_validation_error(exc: ValidationError) -> list[Issue]:
    """Map every Pydantic error to an :class:`Issue` with a stable code."""
    issues: list[Issue] = []
    for err in exc.errors():
        loc = tuple(err["loc"])
        err_type = err["type"]
        path = join_loc(loc)
        code = _CUSTOM_CODES.get(err_type)
        if code is None and len(loc) == 1:
            code = _TOP_LEVEL_CODES.get((str(loc[0]), err_type))
        if code is None:
            code = _TYPE_CODES.get(err_type, Code.SCHEMA_INVALID)
        message = err["msg"] if err_type in _CUSTOM_CODES else f"Trường không hợp lệ: {err['msg']}"
        issues.append(Issue(code=code, message=message, path=path))
    return issues


# ----------------------------------------------------------------------------- graph rules


def validate(scenario: Scenario, rules: Rules | None = None) -> list[Issue]:
    """Return every structural/style issue of ``scenario`` (empty list = valid)."""
    rules = rules or load_rules()
    issues = [*_check_duplicate_ids(scenario), *_check_start_and_success(scenario)]
    for index, screen in enumerate(scenario.screens):
        issues.extend(_check_screen(scenario, screen, f"screens[{index}]", rules))
    issues.extend(_check_reachability(scenario))
    issues.extend(_check_success_conditions(scenario))
    return issues


def _check_duplicate_ids(scenario: Scenario) -> list[Issue]:
    issues: list[Issue] = []
    seen_screens: set[str] = set()
    for index, screen in enumerate(scenario.screens):
        if screen.id in seen_screens:
            issues.append(
                Issue(
                    code=Code.DUPLICATE_SCREEN_ID,
                    message=f"Màn hình '{screen.id}' bị khai báo hai lần.",
                    path=f"screens[{index}].id",
                )
            )
        seen_screens.add(screen.id)
        seen_elements: set[str] = set()
        for e_index, element in enumerate(screen.elements):
            if element.id in seen_elements:
                issues.append(
                    Issue(
                        code=Code.DUPLICATE_ELEMENT_ID,
                        message=f"Phần tử '{element.id}' bị khai báo hai lần trên '{screen.id}'.",
                        path=f"screens[{index}].elements[{e_index}].id",
                    )
                )
            seen_elements.add(element.id)
    return issues


def _check_start_and_success(scenario: Scenario) -> list[Issue]:
    issues: list[Issue] = []
    if scenario.start_screen not in scenario.screens_by_id:
        issues.append(
            Issue(
                code=Code.START_SCREEN_MISSING,
                message=f"Màn hình bắt đầu '{scenario.start_screen}' không tồn tại.",
                path="start_screen",
            )
        )
    target = scenario.screen(scenario.success.screen)
    if target is None:
        issues.append(
            Issue(
                code=Code.SUCCESS_SCREEN_MISSING,
                message=f"Màn hình thành công '{scenario.success.screen}' không tồn tại.",
                path="success.screen",
            )
        )
    elif not target.terminal:
        issues.append(
            Issue(
                code=Code.SUCCESS_SCREEN_NOT_TERMINAL,
                message=f"Màn hình thành công '{target.id}' phải là màn hình kết thúc (terminal).",
                path="success.screen",
            )
        )
    if not any(screen.terminal for screen in scenario.screens):
        issues.append(
            Issue(
                code=Code.NO_TERMINAL_SCREEN,
                message="Kịch bản không có màn hình kết thúc nào (terminal: true).",
                path="screens",
            )
        )
    return issues


def _check_screen(scenario: Scenario, screen: Screen, path: str, rules: Rules) -> list[Issue]:
    issues: list[Issue] = []
    if not screen.terminal and not screen.valid_actions:
        issues.append(
            Issue(
                code=Code.SCREEN_DEAD_END,
                message=f"Màn hình '{screen.id}' không phải kết thúc nhưng không có hành động nào.",
                path=f"{path}.valid_actions",
            )
        )
    issues.extend(_check_actions(scenario, screen, path))
    issues.extend(_check_mistakes(screen, path, rules))
    issues.extend(
        _style_issues(
            screen.coach_line,
            f"{path}.coach_line",
            rules,
            Code.COACH_LINE_TOO_LONG,
            Code.COACH_LINE_BANNED_TERM,
        )
    )
    issues.extend(_check_sensitive_inputs(scenario, screen, path))
    return issues


def _check_actions(scenario: Scenario, screen: Screen, path: str) -> list[Issue]:
    issues: list[Issue] = []
    for index, action in enumerate(screen.valid_actions):
        a_path = f"{path}.valid_actions[{index}]"
        is_tap = isinstance(action, TapAction)
        target = action.tap if is_tap else action.input
        element = screen.element(target)
        if element is None:
            issues.append(
                Issue(
                    code=Code.ACTION_ELEMENT_MISSING,
                    message=f"Hành động trỏ tới phần tử '{target}' không có trên '{screen.id}'.",
                    path=a_path,
                )
            )
        elif is_tap == (element.kind is ElementKind.INPUT):
            issues.append(
                Issue(
                    code=Code.ACTION_KIND_MISMATCH,
                    message=f"Phần tử '{target}' ({element.kind.value}) không hợp với kiểu "
                    "hành động.",
                    path=a_path,
                )
            )
        if action.next not in scenario.screens_by_id:
            issues.append(
                Issue(
                    code=Code.ACTION_SCREEN_MISSING,
                    message=f"Hành động trỏ tới màn hình '{action.next}' không tồn tại.",
                    path=f"{a_path}.next",
                )
            )
        if isinstance(action, InputAction):
            issues.extend(_check_pattern(action.value_pattern, f"{a_path}.value_pattern"))
    return issues


def _check_pattern(pattern: str, path: str) -> list[Issue]:
    try:
        re.compile(pattern)
    except re.error as exc:
        return [
            Issue(
                code=Code.INPUT_PATTERN_INVALID,
                message=f"Biểu thức kiểm tra giá trị không hợp lệ: {exc}.",
                path=path,
            )
        ]
    return []


def _check_mistakes(screen: Screen, path: str, rules: Rules) -> list[Issue]:
    issues: list[Issue] = []
    for index, mistake in enumerate(screen.common_mistakes):
        m_path = f"{path}.common_mistakes[{index}]"
        if screen.element(mistake.tap) is None:
            issues.append(
                Issue(
                    code=Code.MISTAKE_ELEMENT_MISSING,
                    message=f"Lỗi thường gặp trỏ tới phần tử '{mistake.tap}' không có trên "
                    f"'{screen.id}'.",
                    path=m_path,
                )
            )
        issues.extend(
            _style_issues(
                mistake.hint, f"{m_path}.hint", rules, Code.HINT_TOO_LONG, Code.HINT_BANNED_TERM
            )
        )
    return issues


def _style_issues(text: str, path: str, rules: Rules, too_long: Code, banned: Code) -> list[Issue]:
    issues: list[Issue] = []
    sentences = count_sentences(text)
    if sentences > rules.max_sentences:
        issues.append(
            Issue(
                code=too_long,
                message=f"Câu hướng dẫn dài {sentences} câu, tối đa {rules.max_sentences} câu.",
                path=path,
            )
        )
    hits = contains_banned_terms(text, rules.banned_terms)
    if hits:
        issues.append(
            Issue(
                code=banned,
                message="Câu hướng dẫn chứa thuật ngữ bị cấm: " + ", ".join(hits) + ".",
                path=path,
            )
        )
    return issues


def looks_sensitive(element: Element, never_ask: Iterable[str]) -> bool:
    """True when the element id or label contains a ``never_ask`` term (OTP, mật khẩu...)."""
    names = (ascii_slug(element.id), ascii_slug(element.label))
    return any(contains_token(name, ascii_slug(term)) for term in never_ask for name in names)


def _check_sensitive_inputs(scenario: Scenario, screen: Screen, path: str) -> list[Issue]:
    issues: list[Issue] = []
    for index, element in enumerate(screen.elements):
        if element.kind is not ElementKind.INPUT or element.sensitive:
            continue
        if looks_sensitive(element, scenario.never_ask):
            issues.append(
                Issue(
                    code=Code.SENSITIVE_INPUT_UNFLAGGED,
                    message=f"Ô nhập '{element.id}' ({element.label}) là thông tin nhạy cảm "
                    "nhưng chưa đánh dấu sensitive: true.",
                    path=f"{path}.elements[{index}]",
                )
            )
    return issues


def _edges(scenario: Scenario) -> dict[str, set[str]]:
    """Forward graph: screen id → ids of screens its valid actions lead to."""
    known = scenario.screens_by_id
    return {
        screen_id: {a.next for a in screen.valid_actions if a.next in known}
        for screen_id, screen in known.items()
    }


def _bfs(start: Iterable[str], edges: Mapping[str, set[str]]) -> set[str]:
    seen: set[str] = set(start)
    queue = deque(seen)
    while queue:
        for nxt in edges.get(queue.popleft(), ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _check_reachability(scenario: Scenario) -> list[Issue]:
    known = scenario.screens_by_id
    if scenario.start_screen not in known:
        return []
    issues: list[Issue] = []
    edges = _edges(scenario)
    reachable = _bfs([scenario.start_screen], edges)
    for index, screen in enumerate(scenario.screens):
        if screen.id not in reachable:
            issues.append(
                Issue(
                    code=Code.SCREEN_UNREACHABLE,
                    message=f"Màn hình '{screen.id}' không đến được từ '{scenario.start_screen}'.",
                    path=f"screens[{index}]",
                )
            )
    terminals = [s.id for s in scenario.screens if s.terminal]
    if not terminals:
        return issues
    reverse: dict[str, set[str]] = {sid: set() for sid in known}
    for src, targets in edges.items():
        for dst in targets:
            reverse[dst].add(src)
    can_exit = _bfs(terminals, reverse)
    for index, screen in enumerate(scenario.screens):
        if screen.valid_actions and not screen.terminal and screen.id not in can_exit:
            issues.append(
                Issue(
                    code=Code.SCREEN_NO_EXIT,
                    message=f"Từ màn hình '{screen.id}' không có đường nào tới màn hình kết thúc.",
                    path=f"screens[{index}]",
                )
            )
    return issues


def _check_success_conditions(scenario: Scenario) -> list[Issue]:
    input_ids = {e.id for s in scenario.screens for e in s.elements if e.kind is ElementKind.INPUT}
    return [
        Issue(
            code=Code.SUCCESS_CONDITION_UNKNOWN_FIELD,
            message=f"Điều kiện thành công dùng ô nhập '{key}' không có trong kịch bản.",
            path=f"success.conditions.{key}",
        )
        for key in scenario.success.conditions
        if key not in input_ids
    ]


# ----------------------------------------------------------------------------- raw data / files


def validate_data(data: Any, rules: Rules | None = None) -> list[Issue]:
    """Validate a raw JSON object: schema errors first, then graph rules."""
    if not isinstance(data, Mapping):
        return [Issue(code=Code.NOT_AN_OBJECT, message="Kịch bản phải là một đối tượng JSON.")]
    try:
        scenario = Scenario.model_validate(data)
    except ValidationError as exc:
        return issues_from_validation_error(exc)
    return validate(scenario, rules)


def validate_file(path: Path, rules: Rules | None = None) -> list[Issue]:
    """Validate one ``*.json`` file, including that its stem equals the scenario id."""
    if not path.is_file():
        return [Issue(code=Code.FILE_NOT_FOUND, message=f"Không tìm thấy file {path}.")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Issue(code=Code.JSON_INVALID, message=f"File {path.name} không phải JSON: {exc}.")]
    issues = validate_data(data, rules)
    if not issues and data.get("id") != path.stem:
        issues.append(
            Issue(
                code=Code.ID_FILENAME_MISMATCH,
                message=f"id '{data.get('id')}' phải trùng tên file '{path.stem}'.",
                path="id",
            )
        )
    return issues
