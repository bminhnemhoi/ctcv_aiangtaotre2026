from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ctcv_core.config import load_config
from ctcv_core.paths import DRILLS_DIR
from ctcv_drills.rules import load_rules
from ctcv_drills.schema import Drill
from ctcv_drills.validator import (
    Code,
    Issue,
    StyleRules,
    content_issues,
    expected_stem,
    is_multi_turn,
    issues_from_validation_error,
    join_loc,
    load_style,
    raw_issues,
    real_names_in,
    validate,
    validate_data,
    validate_file,
    walk_keys,
    walk_strings,
)

INVALID_DIR = Path(__file__).resolve().parent / "fixtures" / "invalid"
SAMPLE_KEY = "gia-danh-cong-an-goi-dien"
SAMPLE_PATH = DRILLS_DIR / f"{SAMPLE_KEY}.json"
WriteJson = Callable[[Path, Any], Path]


INVALID_FIXTURES = sorted(INVALID_DIR.glob("*.json"))
MIN_INVALID_FIXTURES = 6


def expected_code(path: Path) -> str:
    return path.stem.upper().replace("-", "_").removesuffix("_NESTED")


def codes_of(issues: list[Issue]) -> set[str]:
    return {issue.code for issue in issues}


def test_sample_drill_is_valid(sample: Drill) -> None:
    assert validate(sample) == []
    assert validate_file(SAMPLE_PATH) == []


def test_enough_invalid_fixtures() -> None:
    assert len(INVALID_FIXTURES) >= MIN_INVALID_FIXTURES


@pytest.mark.parametrize("path", INVALID_FIXTURES, ids=lambda p: p.stem)
def test_invalid_fixture_breaks_exactly_one_rule(path: Path) -> None:
    issues = validate_file(path)
    assert codes_of(issues) == {expected_code(path)}, [str(i) for i in issues]
    for issue in issues:
        assert issue.message.strip()
        assert issue.code in set(Code)


def test_full_dialogue_script_is_rejected_before_schema() -> None:
    """Brief §15: a drill carrying a complete multi-turn script never passes."""
    data = json.loads((INVALID_DIR / "forbidden-field.json").read_text(encoding="utf-8"))
    assert isinstance(data["script"], list) and len(data["script"]) >= 4
    issues = validate_data(data)
    assert [(i.code, i.path) for i in issues] == [(Code.FORBIDDEN_FIELD, "script")]
    assert "lời thoại" in issues[0].message


def test_forbidden_field_is_case_insensitive_and_nested() -> None:
    rules = load_rules()
    issues = raw_issues({"a": {"b": [{"Transcript": "x"}]}, "Message": 1}, rules)
    assert [(i.code, i.path) for i in issues] == [
        (Code.FORBIDDEN_FIELD, "a.b[0].Transcript"),
        (Code.FORBIDDEN_FIELD, "Message"),
    ]


def test_walk_helpers() -> None:
    data = {"a": [{"b": "x"}, "y"], "c": {"d": "z"}}
    assert list(walk_keys(data)) == [("a", "a"), ("a[0].b", "b"), ("c", "c"), ("c.d", "d")]
    assert list(walk_strings(data)) == [("a[0].b", "x"), ("a[1]", "y"), ("c.d", "z")]
    assert join_loc(("options", 1, "id")) == "options[1].id"


def test_validate_data_rejects_non_object() -> None:
    assert codes_of(validate_data([1])) == {Code.NOT_AN_OBJECT}


def test_validate_file_missing_and_bad_json(tmp_path: Path) -> None:
    assert codes_of(validate_file(tmp_path / "nope.json")) == {Code.FILE_NOT_FOUND}
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert codes_of(validate_file(bad)) == {Code.JSON_INVALID}


def test_file_name_follows_key_and_variant(
    tmp_path: Path, sample_dict: dict[str, Any], write_json: WriteJson
) -> None:
    assert expected_stem("k", 1) == "k" and expected_stem("k", 3) == "k.v3"
    issues = validate_file(write_json(tmp_path / "ten-khac.json", sample_dict))
    assert codes_of(issues) == {Code.KEY_FILENAME_MISMATCH}
    sample_dict["variant"] = 2
    ok = write_json(tmp_path / "gia-danh-cong-an-goi-dien.v2.json", sample_dict)
    assert validate_file(ok) == []
    wrong = write_json(tmp_path / "gia-danh-cong-an-goi-dien.json", sample_dict)
    assert codes_of(validate_file(wrong)) == {Code.KEY_FILENAME_MISMATCH}


def test_unmapped_pydantic_error_falls_back(sample_dict: dict[str, Any]) -> None:
    sample_dict["severity"] = "cao"
    assert codes_of(validate_data(sample_dict)) == {Code.SCHEMA_INVALID}


def test_nested_slug_error(sample_dict: dict[str, Any]) -> None:
    sample_dict["options"][0]["id"] = "Sai Id"
    issues = validate_data(sample_dict)
    assert [(i.code, i.path) for i in issues] == [(Code.SLUG_INVALID, "options[0].id")]


def test_issues_from_validation_error_direct(sample_dict: dict[str, Any]) -> None:
    del sample_dict["debrief"]
    with pytest.raises(ValidationError) as exc:
        Drill.model_validate(sample_dict)
    issues = issues_from_validation_error(exc.value)
    assert [(i.code, i.path) for i in issues] == [(Code.FIELD_MISSING, "debrief")]


def test_issue_str() -> None:
    assert str(Issue(code="X", message="m", path="p")) == "[X] p: m"
    assert str(Issue(code="X", message="m")) == "[X] m"


@pytest.mark.parametrize(
    "text",
    [
        "[Mô phỏng] Bước 1 bác đọc mã, bước 2 bác chuyển tiền.",
        "[Mô phỏng] Đọc mã cho tôi, sau đó gửi ảnh biên lai.",
        "[Mô phỏng] Câu một.\nCâu hai.",
        "Kẻ lừa đảo: alo. Nạn nhân: alo.",
        "[Mô phỏng] Lượt 2: bác chuyển thêm.",
    ],
)
def test_is_multi_turn(text: str) -> None:
    assert is_multi_turn(text, load_rules())


def test_single_turn_is_ok(sample: Drill) -> None:
    assert not is_multi_turn(sample.utterance, load_rules())


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("Tôi gọi từ Vietcombank", ["Vietcombank"]),
        ("toi goi tu vietcombank", ["Vietcombank"]),
        ("Cán bộ Bộ Công An đây", ["Bộ Công an"]),
        ("Bo cong an", ["Bộ Công an"]),
        ("Tôi ở công an phường", []),
        ("MB", ["MB"]),
        ("mbbank gọi", ["MBBank"]),
        ("Tôi là cán bộ ngân hàng", []),
    ],
)
def test_real_names_in(text: str, names: list[str]) -> None:
    assert real_names_in(text, load_rules()) == names


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("vào www.abc.com ngay", {Code.URL_FOUND}),
        ("vào https://x.y/z ngay", {Code.URL_FOUND}),
        ("vào trang congan-xacminh.vn", {Code.URL_FOUND}),
        ("gọi 0912 345 678", {Code.PHONE_FOUND}),
        ("gọi +84912345678", {Code.PHONE_FOUND}),
        ("tài khoản 1902 3344 55", {Code.DIGIT_RUN_FOUND}),
        ("chuyển 20.000 đồng", set()),
        ("chuyển 200.000 đồng", {Code.DIGIT_RUN_FOUND}),
        ("chuyển 2.000.000 đồng", {Code.DIGIT_RUN_FOUND}),
        ("mã 12345", set()),
        ("Tôi ở Agribank", {Code.REAL_NAME_FOUND}),
        ("một câu bình thường", set()),
    ],
)
def test_content_issues(text: str, codes: set[str]) -> None:
    assert codes_of(content_issues(text, "p", load_rules())) == codes


def test_style_comes_from_guardrails() -> None:
    cfg = load_config("guardrails")
    style = load_style()
    assert style.max_sentences == cfg["max_sentences"]
    assert style.banned_terms == cfg["banned_terms"]


def test_custom_style_is_honoured(sample: Drill) -> None:
    strict = StyleRules(max_sentences=0, banned_terms=["Công an"])
    codes = codes_of(validate(sample, style=strict))
    assert {Code.DEBRIEF_TOO_LONG, Code.BANNED_TERM_FOUND} <= codes


def test_fixture_files_are_well_formed_json() -> None:
    for path in INVALID_FIXTURES:
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict), path.name
