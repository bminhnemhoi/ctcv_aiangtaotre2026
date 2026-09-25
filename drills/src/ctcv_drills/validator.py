"""D27 content validation of scam drills.

:func:`validate` checks a parsed :class:`~ctcv_drills.schema.Drill`;
:func:`validate_data` first walks the **raw** JSON for forbidden field names and
over-long strings, then applies the schema, then the content rules; and
:func:`validate_file` adds the file-name convention. Every :class:`Issue` has a
stable machine ``code`` (:class:`Code`), a Vietnamese ``message`` and a JSON ``path``.

Limits and block lists come from ``ctcv_drills/rules.yaml``; sentence and jargon
limits (``max_sentences``, ``banned_terms``) come from ``config/guardrails.yaml``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ctcv_core.config import load_config
from ctcv_core.text import contains_banned_terms, count_sentences
from ctcv_drills.normalize import ascii_slug, contains_token, word_count
from ctcv_drills.rules import DrillRules, load_rules
from ctcv_drills.schema import SIMULATION_TAG, Drill


class Code(StrEnum):
    """Machine codes for every rule a drill can break."""

    # --- raw JSON ---
    NOT_AN_OBJECT = "NOT_AN_OBJECT"
    FORBIDDEN_FIELD = "FORBIDDEN_FIELD"
    STRING_TOO_LONG = "STRING_TOO_LONG"
    # --- schema (Pydantic) ---
    SCHEMA_INVALID = "SCHEMA_INVALID"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    FIELD_MISSING = "FIELD_MISSING"
    ENUM_INVALID = "ENUM_INVALID"
    SLUG_INVALID = "SLUG_INVALID"
    KEY_INVALID = "KEY_INVALID"
    VARIANT_OUT_OF_RANGE = "VARIANT_OUT_OF_RANGE"
    SEVERITY_OUT_OF_RANGE = "SEVERITY_OUT_OF_RANGE"
    LABEL_INVALID = "LABEL_INVALID"
    OPTIONS_COUNT = "OPTIONS_COUNT"
    OPTIONS_CORRECT_COUNT = "OPTIONS_CORRECT_COUNT"
    OPTION_ID_DUPLICATE = "OPTION_ID_DUPLICATE"
    RED_FLAGS_EMPTY = "RED_FLAGS_EMPTY"
    RED_FLAG_DUPLICATE = "RED_FLAG_DUPLICATE"
    THREE_THINGS_COUNT = "THREE_THINGS_COUNT"
    # --- content (D27) ---
    UTTERANCE_MISSING_TAG = "UTTERANCE_MISSING_TAG"
    UTTERANCE_TOO_LONG = "UTTERANCE_TOO_LONG"
    UTTERANCE_MULTI_TURN = "UTTERANCE_MULTI_TURN"
    PRETEXT_TOO_LONG = "PRETEXT_TOO_LONG"
    DEBRIEF_TOO_LONG = "DEBRIEF_TOO_LONG"
    BANNED_TERM_FOUND = "BANNED_TERM_FOUND"
    URL_FOUND = "URL_FOUND"
    PHONE_FOUND = "PHONE_FOUND"
    DIGIT_RUN_FOUND = "DIGIT_RUN_FOUND"
    REAL_NAME_FOUND = "REAL_NAME_FOUND"
    # --- file ---
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    JSON_INVALID = "JSON_INVALID"
    KEY_FILENAME_MISMATCH = "KEY_FILENAME_MISMATCH"
    DUPLICATE_DRILL = "DUPLICATE_DRILL"


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


class StyleRules(BaseModel):
    """Sentence/jargon limits read from ``config/guardrails.yaml``."""

    max_sentences: int
    banned_terms: list[str | dict[str, str]]


def load_style() -> StyleRules:
    """Read ``max_sentences`` and ``banned_terms`` from ``config/guardrails.yaml``."""
    cfg = load_config("guardrails")
    return StyleRules(max_sentences=cfg["max_sentences"], banned_terms=cfg["banned_terms"])


# ----------------------------------------------------------------------------- raw JSON walk


def _child_path(path: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else str(key)


def walk_keys(obj: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield ``(path, key)`` for every mapping key at any depth."""
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            child = _child_path(path, key)
            yield child, str(key)
            yield from walk_keys(value, child)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from walk_keys(value, _child_path(path, index))


def walk_strings(obj: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield ``(path, text)`` for every string leaf at any depth."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from walk_strings(value, _child_path(path, key))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from walk_strings(value, _child_path(path, index))


def raw_issues(data: Mapping[str, Any], rules: DrillRules) -> list[Issue]:
    """Forbidden field names and over-long strings, checked on the raw JSON."""
    issues = [
        Issue(
            code=Code.FORBIDDEN_FIELD,
            message=f"Trường '{key}' bị cấm: kịch bản không được chứa lời thoại hoàn chỉnh.",
            path=path,
        )
        for path, key in walk_keys(data)
        if key.casefold() in rules.forbidden_field_set
    ]
    issues.extend(
        Issue(
            code=Code.STRING_TOO_LONG,
            message=f"Chuỗi dài {len(text)} ký tự, tối đa {rules.max_string_chars}.",
            path=path,
        )
        for path, text in walk_strings(data)
        if len(text) > rules.max_string_chars
    )
    return issues


# ----------------------------------------------------------------------------- schema errors

_CUSTOM_CODES: dict[str, Code] = {
    "options_correct_count": Code.OPTIONS_CORRECT_COUNT,
    "option_id_duplicate": Code.OPTION_ID_DUPLICATE,
    "red_flag_duplicate": Code.RED_FLAG_DUPLICATE,
}
_TOP_LEVEL_CODES: dict[tuple[str, str], Code] = {
    ("key", "string_pattern_mismatch"): Code.KEY_INVALID,
    ("variant", "greater_than_equal"): Code.VARIANT_OUT_OF_RANGE,
    ("variant", "less_than_equal"): Code.VARIANT_OUT_OF_RANGE,
    ("severity", "greater_than_equal"): Code.SEVERITY_OUT_OF_RANGE,
    ("severity", "less_than_equal"): Code.SEVERITY_OUT_OF_RANGE,
    ("label", "literal_error"): Code.LABEL_INVALID,
    ("options", "too_short"): Code.OPTIONS_COUNT,
    ("options", "too_long"): Code.OPTIONS_COUNT,
    ("three_things", "too_short"): Code.THREE_THINGS_COUNT,
    ("three_things", "too_long"): Code.THREE_THINGS_COUNT,
    ("red_flags", "too_short"): Code.RED_FLAGS_EMPTY,
}
_TYPE_CODES: dict[str, Code] = {
    "extra_forbidden": Code.UNKNOWN_FIELD,
    "missing": Code.FIELD_MISSING,
    "enum": Code.ENUM_INVALID,
    "string_too_long": Code.STRING_TOO_LONG,
    "string_pattern_mismatch": Code.SLUG_INVALID,
}


def join_loc(loc: tuple[Any, ...]) -> str:
    """Render a Pydantic ``loc`` tuple as ``options[1].id``."""
    path = ""
    for part in loc:
        path = _child_path(path, part)
    return path


def issues_from_validation_error(exc: ValidationError) -> list[Issue]:
    """Map every Pydantic error to an :class:`Issue` with a stable code."""
    issues: list[Issue] = []
    for err in exc.errors():
        loc = tuple(err["loc"])
        err_type = err["type"]
        code = _CUSTOM_CODES.get(err_type)
        if code is None and len(loc) == 1:
            code = _TOP_LEVEL_CODES.get((str(loc[0]), err_type))
        if code is None:
            code = _TYPE_CODES.get(err_type, Code.SCHEMA_INVALID)
        message = err["msg"] if err_type in _CUSTOM_CODES else f"Trường không hợp lệ: {err['msg']}"
        issues.append(Issue(code=code, message=message, path=join_loc(loc)))
    return issues


# ----------------------------------------------------------------------------- content rules


def validate(
    drill: Drill, rules: DrillRules | None = None, style: StyleRules | None = None
) -> list[Issue]:
    """Return every D27 content issue of ``drill`` (empty list = valid)."""
    rules = rules or load_rules()
    style = style or load_style()
    issues = _check_utterance(drill.utterance, rules)
    issues.extend(_check_pretext(drill.pretext, rules))
    issues.extend(_check_debrief(drill, style))
    for path, text in walk_strings(drill.model_dump(mode="json")):
        issues.extend(content_issues(text, path, rules))
    return issues


def _check_utterance(text: str, rules: DrillRules) -> list[Issue]:
    issues: list[Issue] = []
    if SIMULATION_TAG not in text:
        issues.append(
            Issue(
                code=Code.UTTERANCE_MISSING_TAG,
                message=f'utterance phải chứa nhãn "{SIMULATION_TAG}".',
                path="utterance",
            )
        )
    words = word_count(text)
    if words > rules.utterance_max_words:
        issues.append(
            Issue(
                code=Code.UTTERANCE_TOO_LONG,
                message=f"utterance dài {words} từ, tối đa {rules.utterance_max_words} từ.",
                path="utterance",
            )
        )
    if is_multi_turn(text, rules):
        issues.append(
            Issue(
                code=Code.UTTERANCE_MULTI_TURN,
                message="utterance chỉ được là một lượt nói, không xuống dòng, "
                "không có dấu hiệu leo thang nhiều bước.",
                path="utterance",
            )
        )
    return issues


def is_multi_turn(text: str, rules: DrillRules) -> bool:
    """True when ``text`` reads like several turns or a step-by-step script."""
    folded = text.casefold()
    if any(marker.casefold() in folded for marker in rules.escalation_markers):
        return True
    return any(pattern.search(text) for pattern in rules.escalation_res)


def _check_pretext(text: str, rules: DrillRules) -> list[Issue]:
    words = word_count(text)
    if words > rules.pretext_max_words:
        return [
            Issue(
                code=Code.PRETEXT_TOO_LONG,
                message=f"pretext dài {words} từ, tối đa {rules.pretext_max_words} từ.",
                path="pretext",
            )
        ]
    return []


def _check_debrief(drill: Drill, style: StyleRules) -> list[Issue]:
    issues: list[Issue] = []
    sentences = count_sentences(drill.debrief)
    if sentences > style.max_sentences:
        issues.append(
            Issue(
                code=Code.DEBRIEF_TOO_LONG,
                message=f"debrief dài {sentences} câu, tối đa {style.max_sentences} câu.",
                path="debrief",
            )
        )
    spoken = [("debrief", drill.debrief)]
    spoken.extend((f"three_things[{i}]", t) for i, t in enumerate(drill.three_things))
    for path, text in spoken:
        hits = contains_banned_terms(text, style.banned_terms)
        if hits:
            issues.append(
                Issue(
                    code=Code.BANNED_TERM_FOUND,
                    message="Chứa thuật ngữ bị cấm: " + ", ".join(hits) + ".",
                    path=path,
                )
            )
    return issues


def real_names_in(text: str, rules: DrillRules) -> list[str]:
    """Block-listed real names present in ``text`` (case- and diacritics-insensitive)."""
    plain = ascii_slug(text, " ")
    return [name for name in rules.real_names if contains_token(plain, ascii_slug(name, " "))]


def content_issues(text: str, path: str, rules: DrillRules) -> list[Issue]:
    """URL, phone number, digit run and real-name checks for one string."""
    issues: list[Issue] = []
    if rules.url_re.search(text):
        issues.append(
            Issue(code=Code.URL_FOUND, message="Không được chứa link/tên miền.", path=path)
        )
    remainder = text
    if rules.phone_re.search(text):
        issues.append(
            Issue(code=Code.PHONE_FOUND, message="Không được chứa số điện thoại.", path=path)
        )
        remainder = rules.phone_re.sub(" ", text)
    if rules.digit_run_re.search(remainder):
        issues.append(
            Issue(
                code=Code.DIGIT_RUN_FOUND,
                message=f"Không được chứa dãy từ {rules.min_digit_run} chữ số "
                "(số tài khoản, số tiền viết bằng chữ).",
                path=path,
            )
        )
    names = real_names_in(text, rules)
    if names:
        issues.append(
            Issue(
                code=Code.REAL_NAME_FOUND,
                message="Không dùng tên ngân hàng/cơ quan thật: " + ", ".join(names) + ".",
                path=path,
            )
        )
    return issues


# ----------------------------------------------------------------------------- raw data / files


def validate_data(
    data: Any, rules: DrillRules | None = None, style: StyleRules | None = None
) -> list[Issue]:
    """Validate a raw JSON object: forbidden fields → schema → content rules."""
    rules = rules or load_rules()
    if not isinstance(data, Mapping):
        return [Issue(code=Code.NOT_AN_OBJECT, message="Kịch bản phải là một đối tượng JSON.")]
    blocking = raw_issues(data, rules)
    if blocking:
        return blocking
    try:
        drill = Drill.model_validate(data)
    except ValidationError as exc:
        return issues_from_validation_error(exc)
    return validate(drill, rules, style)


def expected_stem(key: str, variant: int) -> str:
    """File stem for a drill: ``<key>`` for variant 1, ``<key>.v<n>`` otherwise."""
    return key if variant == 1 else f"{key}.v{variant}"


def validate_file(
    path: Path, rules: DrillRules | None = None, style: StyleRules | None = None
) -> list[Issue]:
    """Validate one ``*.json`` file, including the file-name convention."""
    if not path.is_file():
        return [Issue(code=Code.FILE_NOT_FOUND, message=f"Không tìm thấy file {path}.")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Issue(code=Code.JSON_INVALID, message=f"File {path.name} không phải JSON: {exc}.")]
    issues = validate_data(data, rules, style)
    if issues:
        return issues
    stem = expected_stem(str(data.get("key")), int(data.get("variant", 1)))
    if stem != path.stem:
        issues.append(
            Issue(
                code=Code.KEY_FILENAME_MISMATCH,
                message=f"Tên file phải là '{stem}.json' (theo key và variant).",
                path="key",
            )
        )
    return issues
