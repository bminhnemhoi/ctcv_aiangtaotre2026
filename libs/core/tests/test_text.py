from __future__ import annotations

import pytest

from ctcv_core.text import contains_banned_terms, count_sentences

SENTENCE_SAMPLES = [
    ("Bác bấm nút xanh có chữ Quét QR nhé.", 1),
    ("Bác muốn chuyển tiền cho con hay trả tiền hàng? Bác nói cho cháu biết nhé.", 2),
    ("Một. Hai. Ba.", 3),
    ("Bác chờ chút… cháu xem đã.", 1),
    ("Bác chờ chút... cháu xem đã.", 1),
    ("Xong rồi… Giờ bác bấm nút xanh nhé.", 2),
    ("Cháu ở TP. Hồ Chí Minh, gần Q. 1.", 1),
    ("Bác nhập 200.000đ rồi bấm Tiếp tục.", 1),
    ("Giá 3,5 triệu. Bác trả được không?", 2),
    ("Bác chọn mục 1. Sau đó bấm Tiếp.", 2),
    ("Không có dấu chấm", 1),
    ("Tuyệt vời!! Bác làm được rồi.", 2),
    ("Bác bấm 'Đồng ý'. Rồi chờ.", 2),
    ("Bác gặp ThS. Nguyễn Văn A. Anh ấy sẽ giúp.", 2),
    ("Vậy mình chuyển cho con nhé. Bác bấm nút xanh có chữ Quét QR ở giữa màn hình nhé.", 2),
    ("Bác bấm nút xanh nhé!", 1),
    ("Cháu học ở T.P. Hồ Chí Minh.", 1),
    ("Đó là quảng cáo thôi, không sao đâu bác. Bác bấm nút xanh có chữ Quét QR nhé.", 2),
]


@pytest.mark.parametrize(("text", "expected"), SENTENCE_SAMPLES)
def test_count_sentences(text: str, expected: int) -> None:
    assert count_sentences(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_count_sentences_empty(text: str) -> None:
    assert count_sentences(text) == 0


def test_count_sentences_extra_abbreviation() -> None:
    assert count_sentences("Gặp Cty. ABC nhé.") == 2
    assert count_sentences("Gặp Cty. ABC nhé.", extra_abbreviations=["Cty"]) == 1


def test_count_sentences_three_is_over_limit() -> None:
    text = "Bác mở ứng dụng. Bác bấm Quét QR. Bác đưa máy vào mã."
    assert count_sentences(text) == 3


def test_contains_banned_terms_plain_strings() -> None:
    hits = contains_banned_terms(
        "Bác cần xác thực rồi Đăng Xuất, token nhé", ["token", "xác thực", "đăng xuất"]
    )
    assert hits == ["xác thực", "đăng xuất", "token"]


def test_contains_banned_terms_mapping_shape() -> None:
    banned = [
        {"term": "giao diện", "replacement": "màn hình"},
        {"term": "menu", "replacement": "danh sách"},
    ]
    assert contains_banned_terms("Mở menu ở giao diện chính", banned) == ["menu", "giao diện"]


def test_contains_banned_terms_whole_word_only() -> None:
    assert contains_banned_terms("tokenizer và tabular", ["token", "tab"]) == []
    assert contains_banned_terms("bấm tab kia", ["tab"]) == ["tab"]


def test_contains_banned_terms_none() -> None:
    assert contains_banned_terms("Bác bấm nút xanh nhé.", ["token"]) == []
    assert contains_banned_terms("", ["token"]) == []
    assert contains_banned_terms("token", []) == []


def test_contains_banned_terms_dedupes_case_variants() -> None:
    assert contains_banned_terms("Token token TOKEN", ["token", "Token"]) == ["token"]
