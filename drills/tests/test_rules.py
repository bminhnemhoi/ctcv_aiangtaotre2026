from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctcv_drills.rules import DrillRules, load_rules


def test_rules_are_cached_and_match_d27() -> None:
    rules = load_rules()
    assert rules is load_rules()
    assert rules.utterance_max_words == 40 and rules.pretext_max_words == 30
    assert rules.max_string_chars == 200 and rules.min_digit_run == 6
    assert {"script", "dialogue", "message", "transcript", "turns"} <= rules.forbidden_field_set
    banks = {"Vietcombank", "BIDV", "Agribank", "Techcombank", "MB", "VPBank"}
    assert banks <= set(rules.real_names)
    assert {"Công an TP", "Bộ Công an", "Cục Thuế"} <= set(rules.real_names)
    assert {"bước 2", "sau đó gửi"} <= set(rules.escalation_markers)


def test_digit_run_regex() -> None:
    pattern = load_rules().digit_run_re
    assert pattern.search("123456") and pattern.search("12 34 56") and pattern.search("1.234.567")
    assert not pattern.search("12345") and not pattern.search("1 2")


def test_rules_reject_unknown_keys() -> None:
    data = load_rules().model_dump()
    data["la"] = 1
    with pytest.raises(ValidationError):
        DrillRules.model_validate(data)
