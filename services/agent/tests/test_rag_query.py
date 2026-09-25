"""ADR-007 C4: query normalisation, accent folding, tokens and synonym expansion."""

from __future__ import annotations

import dataclasses
import unicodedata

import pytest

from ctcv_agent.rag.query import (
    content_tokens,
    expand_synonyms,
    fold_accents,
    normalize_query,
    syllable_bigrams,
)
from ctcv_agent.rag.settings import RagSettings, load_rag_settings


@pytest.fixture
def settings() -> RagSettings:
    return load_rag_settings()


def _no_fold(settings: RagSettings) -> RagSettings:
    retrieval = dataclasses.replace(settings.retrieval, accent_fold=False)
    return dataclasses.replace(settings, retrieval=retrieval)


# --------------------------------------------------------------------------- normalize_query


def test_normalize_composes_casefolds_and_collapses_whitespace(settings: RagSettings) -> None:
    decomposed = unicodedata.normalize("NFD", "  Đăng KÝ\tthường   TRÚ \n")
    assert normalize_query(decomposed, settings) == "đăng ký thường trú"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Làm căn cước cần chi?", "làm căn cước cần gì?"),
        ("mang chi theo", "mang gì theo"),
        ("Làm răng để đăng ký tạm trú", "làm sao để đăng ký tạm trú"),
        ("mần răng", "làm sao"),
        ("nộp ở mô", "nộp ở đâu"),
        ("hết bi nhiêu tiền", "hết bao nhiêu tiền"),
        ("bao nhiu ngày", "bao nhiêu ngày"),
        ("có mất tiền hông", "có mất tiền không"),
    ],
)
def test_dialect_phrases_are_rewritten(settings: RagSettings, question: str, expected: str) -> None:
    assert normalize_query(question, settings) == expected


@pytest.mark.parametrize(
    "question",
    [
        "chi phí đăng ký thường trú",
        "cần chi phí bao nhiêu",
        "làm chi tiết hồ sơ",
        "không mất tiền",
        "khônghông",
        "cần chiếc thẻ",
    ],
)
def test_standard_words_are_not_rewritten(settings: RagSettings, question: str) -> None:
    assert normalize_query(question, settings) == question


def test_normalize_loads_settings_when_omitted() -> None:
    assert normalize_query("Cần CHI") == "cần gì"


def test_rewrites_do_not_cascade(settings: RagSettings) -> None:
    extra = (*settings.retrieval.dialect_phrases, ("cần gì", "CASCADE"))
    retrieval = dataclasses.replace(settings.retrieval, dialect_phrases=extra)
    custom = dataclasses.replace(settings, retrieval=retrieval)
    assert normalize_query("cần chi", custom) == "cần gì"


# --------------------------------------------------------------------------- fold_accents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("căn cước", "can cuoc"),
        ("Đăng ký thường trú", "Dang ky thuong tru"),
        ("đ", "d"),
        ("lệ phí", "le phi"),
        ("abc 123", "abc 123"),
    ],
)
def test_fold_accents(text: str, expected: str) -> None:
    assert fold_accents(text) == expected


def test_unaccented_query_matches_accented(settings: RagSettings) -> None:
    plain = fold_accents(normalize_query("lam can cuoc", settings))
    accented = fold_accents(normalize_query("Làm căn cước", settings))
    assert plain == accented == "lam can cuoc"
    assert [fold_accents(t) for t in content_tokens("làm căn cước")] == content_tokens(
        "lam can cuoc"
    )


# --------------------------------------------------------------------------- tokens


def test_content_tokens_drop_stopwords_and_keep_order() -> None:
    assert content_tokens("Lệ phí của bác và cháu là bao nhiêu") == [
        "lệ",
        "phí",
        "bao",
        "nhiêu",
    ]


def test_content_tokens_casefold_and_keep_digits() -> None:
    assert content_tokens("Mẫu CT01, 20.000 đồng") == ["mẫu", "ct01", "20", "000", "đồng"]


def test_content_tokens_empty() -> None:
    assert content_tokens("  ,.? ") == []


def test_syllable_bigrams() -> None:
    assert syllable_bigrams(["đăng", "ký", "tạm", "trú"]) == ["đăng_ký", "ký_tạm", "tạm_trú"]
    assert syllable_bigrams(["một"]) == []
    assert syllable_bigrams([]) == []


# --------------------------------------------------------------------------- synonyms


def test_expand_synonyms_returns_other_members(settings: RagSettings) -> None:
    extra = expand_synonyms("làm căn cước ở đâu", settings)
    assert {"cccd", "thẻ căn cước"} <= set(extra)
    assert "căn cước" not in extra


def test_can_cuoc_does_not_expand_to_cmnd(settings: RagSettings) -> None:
    # Regression (live check 25/9): the KB has separate CMND procedures ("Cấp xác nhận số
    # chứng minh nhân dân 09 số"); one shared group sent "làm căn cước cần mang chi" there.
    assert not {"chứng minh nhân dân", "cmnd"} & set(expand_synonyms("làm căn cước", settings))
    assert expand_synonyms("cấp lại cmnd", settings) == ["chứng minh nhân dân"]


def test_expand_synonyms_matches_unaccented_queries(settings: RagSettings) -> None:
    extra = expand_synonyms("lam can cuoc", settings)
    assert "căn cước" in extra
    assert "cccd" in extra


def test_expand_synonyms_without_accent_folding(settings: RagSettings) -> None:
    assert expand_synonyms("lam can cuoc", _no_fold(settings)) == []
    assert "cccd" in expand_synonyms("làm căn cước", _no_fold(settings))


def test_expand_synonyms_from_colloquial_word(settings: RagSettings) -> None:
    assert expand_synonyms("Nhập HỘ KHẨU cho con", settings) == ["thường trú"]


def test_expand_synonyms_excludes_members_already_present(settings: RagSettings) -> None:
    extra = expand_synonyms("cấp thẻ căn cước", settings)
    assert "căn cước" not in extra
    assert "thẻ căn cước" not in extra
    # Was ["cccd", "chứng minh nhân dân", "cmnd"] before the căn cước / CMND groups were split.
    assert extra == ["cccd"]


def test_expand_synonyms_needs_whole_words(settings: RagSettings) -> None:
    assert expand_synonyms("xe biển số đẹp", settings) == ["đăng ký xe", "cà vẹt"]
    assert expand_synonyms("lý lịch", settings) == ["lý lịch tư pháp"]
    assert expand_synonyms("gplxx", settings) == []


def test_expand_synonyms_no_match(settings: RagSettings) -> None:
    assert expand_synonyms("đăng ký kết hôn", settings) == []


def test_expand_synonyms_is_deduplicated_and_stable(settings: RagSettings) -> None:
    first = expand_synonyms("hộ chiếu và passport, căn cước", settings)
    assert first == expand_synonyms("hộ chiếu và passport, căn cước", settings)
    assert len(first) == len(set(first))
    assert "passport" not in first and "hộ chiếu" not in first


def test_normalize_without_dialect_phrases(settings: RagSettings) -> None:
    retrieval = dataclasses.replace(settings.retrieval, dialect_phrases=())
    custom = dataclasses.replace(settings, retrieval=retrieval)
    assert normalize_query("  Cần   CHI ", custom) == "cần chi"
