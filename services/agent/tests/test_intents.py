"""Intent detection from config/rag.yaml ``intents`` (priority = key order)."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from ctcv_agent.intents import FALLBACK_INTENT, detect_intent, phrase_regex
from ctcv_agent.rag.settings import RagSettings, load_rag_settings


@pytest.fixture(scope="module")
def settings() -> RagSettings:
    return load_rag_settings()


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("Đăng ký thường trú mất bao nhiêu tiền?", "phi_le_phi"),
        ("Lệ phí làm hộ chiếu", "phi_le_phi"),
        ("Làm căn cước bao lâu thì có?", "thoi_han"),
        ("Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?", "thanh_phan_ho_so"),
        ("Thủ tục đăng ký kết hôn cần những gì?", "thanh_phan_ho_so"),
        ("Đăng ký tạm trú nộp ở đâu?", "noi_nop"),
        ("Có tờ khai đăng ký tạm trú không?", "bieu_mau"),
        ("Điều kiện đăng ký thường trú", "dieu_kien"),
        ("Đăng ký thường trú theo luật nào?", "can_cu_phap_ly"),
        ("Đăng ký thường trú làm thế nào?", "trinh_tu"),
        ("Đăng ký thường trú", FALLBACK_INTENT),
    ],
)
def test_detects_intent_from_config_phrases(
    question: str, intent: str, settings: RagSettings
) -> None:
    assert detect_intent(question, settings) == intent


def test_priority_follows_key_order(settings: RagSettings) -> None:
    # "phí" (phi_le_phi) and "bao lâu" (thoi_han) both match: phi_le_phi comes first.
    assert detect_intent("Làm hộ chiếu bao lâu và lệ phí thế nào?", settings) == "phi_le_phi"


def test_unaccented_question_matches(settings: RagSettings) -> None:
    assert detect_intent("dang ky thuong tru mat bao nhieu tien", settings) == "phi_le_phi"
    assert detect_intent("lam can cuoc can giay to gi", settings) == "thanh_phan_ho_so"
    assert detect_intent("nop o dau", settings) == "noi_nop"


def test_dialect_phrase_is_normalised_first(settings: RagSettings) -> None:
    assert detect_intent("Làm căn cước cần chi rứa?", settings) == "thanh_phan_ho_so"
    assert detect_intent("Đăng ký tạm trú ở mô?", settings) == "noi_nop"


def test_an_accented_word_never_matches_a_different_accented_phrase(
    settings: RagSettings,
) -> None:
    # "màu" (colour) and "mẫu" (form) fold to the same letters; only unaccented text may match.
    assert detect_intent("nút màu xanh ở chỗ này", settings) != "bieu_mau"
    assert detect_intent("cho tôi xin mau to khai", settings) == "bieu_mau"


def test_phrases_match_whole_words_only(settings: RagSettings) -> None:
    assert detect_intent("phía trước cổng", settings) == FALLBACK_INTENT


def test_phrase_regex_accepts_mixed_accents() -> None:
    pattern = phrase_regex("lệ phí")
    assert pattern.search("le phí bao nhiêu")
    assert pattern.search("lệ phi")
    assert not pattern.search("lễ phí")


def test_custom_intents_mapping_is_respected(settings: RagSettings) -> None:
    custom = dataclasses.replace(
        settings, intents=MappingProxyType({"thoi_han": ("bao lâu",), "phi_le_phi": ("phí",)})
    )
    assert detect_intent("phí và bao lâu", custom) == "thoi_han"
