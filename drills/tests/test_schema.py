from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ctcv_drills.schema import (
    LABEL,
    MAX_OPTIONS,
    MIN_OPTIONS,
    SIMULATION_TAG,
    THREE_THINGS_COUNT,
    Channel,
    Drill,
    Impersonates,
    Option,
    RedFlag,
)

BRIEF_IMPERSONATES = {
    "cong-an",
    "thue",
    "ngan-hang",
    "shipper",
    "trung-thuong",
    "nguoi-than",
    "dien-luc",
    "buu-dien",
}
BRIEF_RED_FLAGS = {
    "giuc-chuyen-tien",
    "doi-otp",
    "xung-co-quan",
    "link-la",
    "doa-dam",
    "yeu-cau-cai-app",
    "giu-bi-mat",
    "tai-khoan-la",
}


def test_enums_match_brief() -> None:
    assert {c.value for c in Channel} == {"sms", "zalo", "call"}
    assert {i.value for i in Impersonates} == BRIEF_IMPERSONATES
    assert {r.value for r in RedFlag} == BRIEF_RED_FLAGS


def test_constants() -> None:
    assert LABEL == "Đây là mô phỏng"
    assert SIMULATION_TAG == "[Mô phỏng]"
    assert (MIN_OPTIONS, MAX_OPTIONS, THREE_THINGS_COUNT) == (3, 4, 3)


def test_sample_parses(sample: Drill) -> None:
    assert sample.key == "gia-danh-cong-an-goi-dien"
    assert sample.channel is Channel.CALL and sample.impersonates is Impersonates.CONG_AN
    assert sample.variant == 1 and sample.label == LABEL
    assert SIMULATION_TAG in sample.utterance
    assert len(sample.three_things) == THREE_THINGS_COUNT
    assert sample.correct_option.id == "cup-may"
    assert sample.option("cup-may") is sample.correct_option
    assert sample.option("khong-co") is None


def first_error_type(data: dict[str, Any]) -> str:
    with pytest.raises(ValidationError) as exc:
        Drill.model_validate(data)
    return exc.value.errors()[0]["type"]


def test_exactly_one_correct_option(sample_dict: dict[str, Any]) -> None:
    sample_dict["options"][0]["correct"] = True
    assert first_error_type(sample_dict) == "options_correct_count"
    for option in sample_dict["options"]:
        option["correct"] = False
    assert first_error_type(sample_dict) == "options_correct_count"


def test_option_ids_unique(sample_dict: dict[str, Any]) -> None:
    sample_dict["options"][1]["id"] = sample_dict["options"][0]["id"]
    assert first_error_type(sample_dict) == "option_id_duplicate"


@pytest.mark.parametrize("count", [2, 5])
def test_options_count(sample_dict: dict[str, Any], count: int) -> None:
    options = sample_dict["options"]
    while len(options) < count:
        options.append({"id": f"them-{len(options)}", "text": "Lựa chọn thêm", "correct": False})
    sample_dict["options"] = options[:count]
    assert first_error_type(sample_dict) in {"too_short", "too_long"}


@pytest.mark.parametrize("count", [2, 4])
def test_three_things_is_exactly_three(sample_dict: dict[str, Any], count: int) -> None:
    sample_dict["three_things"] = ["Một việc"] * count
    assert first_error_type(sample_dict) in {"too_short", "too_long"}


def test_label_is_constant(sample_dict: dict[str, Any]) -> None:
    sample_dict["label"] = "Đây là thật"
    assert first_error_type(sample_dict) == "literal_error"


@pytest.mark.parametrize(
    ("field", "value"),
    [("variant", 0), ("variant", 6), ("severity", 0), ("severity", 4)],
)
def test_ranges(sample_dict: dict[str, Any], field: str, value: int) -> None:
    sample_dict[field] = value
    assert first_error_type(sample_dict) in {"greater_than_equal", "less_than_equal"}


def test_key_slug(sample_dict: dict[str, Any]) -> None:
    sample_dict["key"] = "Gia Danh"
    assert first_error_type(sample_dict) == "string_pattern_mismatch"


def test_red_flags_unique_and_non_empty(sample_dict: dict[str, Any]) -> None:
    sample_dict["red_flags"] = ["doa-dam", "doa-dam"]
    assert first_error_type(sample_dict) == "red_flag_duplicate"
    sample_dict["red_flags"] = []
    assert first_error_type(sample_dict) == "too_short"


def test_unknown_field_rejected(sample_dict: dict[str, Any]) -> None:
    sample_dict["script"] = "..."
    assert first_error_type(sample_dict) == "extra_forbidden"


def test_option_model() -> None:
    option = Option(id="cup-may", text="Cúp máy", correct=True)
    assert option.correct
    with pytest.raises(ValidationError):
        Option(id="Cup May", text="x", correct=False)
