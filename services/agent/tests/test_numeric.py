"""Canonical number extraction and the "every number comes from the source" check."""

from __future__ import annotations

import pytest

from ctcv_agent.numeric import (
    NumberCheck,
    canonical_numbers,
    money_amounts,
    numbers_supported,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("lệ phí 20.000 đồng", {"20000"}),
        ("20,000 đồng", {"20000"}),
        ("07 Ngày làm việc", {"7"}),
        ("0 đồng", {"0"}),
        ("mã 1.004222", {"1004222"}),
        ("Thông tư số 66/2023/TT-BCA", {"66", "2023"}),
        ("không có số nào", set()),
        ("", set()),
    ],
)
def test_digit_tokens_are_canonicalised(text: str, expected: set[str]) -> None:
    assert canonical_numbers(text) == expected


def test_trailing_punctuation_is_not_part_of_the_number() -> None:
    assert canonical_numbers("thu 10.000 đồng/lần đăng ký.") == {"10000"}
    assert canonical_numbers("(07).") == {"7"}


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("20 nghìn đồng", "20000"),
        ("20 ngàn", "20000"),
        ("2 triệu đồng", "2000000"),
        ("1,5 triệu", "1500000"),
    ],
)
def test_scale_words_add_the_scaled_value(text: str, value: str) -> None:
    numbers = canonical_numbers(text)
    assert value in numbers


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("mang một bản sao", "1"),
        ("trong ba ngày", "3"),
        ("Năm năm", "5"),
        ("mười tháng", "10"),
        ("hai đồng", "2"),
        ("bảy ngày làm việc", "7"),
    ],
)
def test_number_words_before_units_become_digits(text: str, value: str) -> None:
    assert value in canonical_numbers(text)


def test_number_words_without_unit_are_ignored() -> None:
    assert canonical_numbers("hai trăm nghìn") == set()
    assert canonical_numbers("một cửa") == set()


def test_supported_when_every_number_is_in_a_source() -> None:
    check = numbers_supported(
        "Nộp trực tiếp 20.000 đồng trong 07 ngày",
        ["thu 20.000 đồng/lần", "Trực tiếp: 7 Ngày làm việc"],
    )
    assert check == NumberCheck(ok=True, unsupported=())


def test_invented_number_is_reported() -> None:
    check = numbers_supported("Lệ phí là 15.000 đồng", ["thu 20.000 đồng/lần"])
    assert check.ok is False
    assert check.unsupported == ("15000",)


def test_scaled_answer_matches_plain_source_and_back() -> None:
    assert numbers_supported("mất 20 nghìn đồng", ["thu 20.000 đồng"]).ok
    assert numbers_supported("mất 20.000 đồng", ["thu 20 nghìn đồng"]).ok
    assert not numbers_supported("mất 30 nghìn đồng", ["thu 20.000 đồng"]).ok


def test_word_number_must_also_be_in_source() -> None:
    assert numbers_supported("trong bảy ngày", ["07 ngày làm việc"]).ok
    assert not numbers_supported("trong ba ngày", ["07 ngày làm việc"]).ok


def test_answer_without_numbers_is_always_supported() -> None:
    assert numbers_supported("Bác mang tờ khai nhé", []).ok
    assert numbers_supported("", ["20.000"]).ok


def test_unsupported_numbers_are_sorted_and_unique() -> None:
    check = numbers_supported("5 ngày, 3 ngày, 5 ngày và 12 tháng", ["không"])
    assert check.unsupported == ("12", "3", "5")


def test_letter_digit_codes_are_kept_whole() -> None:
    # A form or law code is not a quantity: "CT02" must not vouch for "hai bản" (2).
    assert canonical_numbers("Mẫu CT02 và DC01") == {"ct02", "dc01"}
    assert canonical_numbers("Luật 68/2020/QH14") == {"68", "2020", "qh14"}
    assert not numbers_supported("mang hai bản sao", ["Mẫu CT02"]).ok
    assert not numbers_supported("dùng mẫu CT09", ["Mẫu CT01"]).ok
    assert numbers_supported("dùng mẫu ct01", ["Mẫu CT01"]).ok


def test_unit_letters_after_a_number_do_not_make_a_code() -> None:
    assert canonical_numbers("20.000đ") == {"20000"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Trường hợp công dân nộp hồ sơ trực tiếp thu 20.000 đồng/lần đăng ký", {20000}),
        ("Lệ phí : 50.000đ/giấy thông hành (Thông tư số 25/2021/TT-BTC ngày 07/4/2021)", {50000}),
        (
            "160.000/hộ chiếu, cấp lại do bị mất: 320.000đ/hộ chiếu (hết ngày 31/12/2023)",
            {160000, 320000},
        ),
        ("Lệ phí : 25.000 Đồng (25.000.000đ/giấy thông hành)", {25000, 25000000}),
        ("200.000 VNĐ/giấy phép", {200000}),
        ("1.000.000đ/thẻ ABTC", {1000000}),
        ("thu 500 đồng mỗi bản", {500}),
        ("10 USD/lần", set()),
        ("Thông tư số 60/2023/TT-BTC ngày 07/9/2023", set()),
        ("Không", set()),
        ("", set()),
    ],
)
def test_money_amounts_reads_only_amounts_written_as_money(text: str, expected: set[int]) -> None:
    # Fee sentences are checked against the wording of phi_le_phi, not only phi_vnd (P1:
    # the parser missed "160.000/hộ chiếu" and kept a mistyped "25.000.000đ").
    assert money_amounts(text) == expected


# ----------------------------------------------------------------------------- units (F-01)
def test_foreign_currency_needs_the_same_currency_in_the_source() -> None:
    # Red-team TL-08: "160.000 đô la" passed because only the digits were compared.
    source = ["160.000/hộ chiếu, cấp lại do bị mất: 320.000đ/hộ chiếu"]
    assert not numbers_supported("Làm hộ chiếu mất 160.000 đô la", source).ok
    assert not numbers_supported("mất 320.000 USD", source).ok
    assert numbers_supported("mất 10 đô la", ["Lệ phí: 10 USD/lần"]).ok


def test_time_unit_must_match_the_source_unit() -> None:
    # Red-team IC-A04: "7 tháng" passed against "07 Ngày làm việc".
    source = ["Trực tiếp: 07 Ngày làm việc"]
    assert not numbers_supported("Thời hạn giải quyết là 7 tháng", source).ok
    assert not numbers_supported("trong 7 năm", source).ok
    assert numbers_supported("trong 7 ngày làm việc", source).ok
    assert numbers_supported("khoảng 7 hôm", source).ok
    assert numbers_supported("trong 15 ngày", ["không quá 15 (mười lăm) ngày"]).ok


def test_scaled_amount_needs_the_scaled_value_in_the_source() -> None:
    # Reviewer: "phí 7 triệu đồng" passed thanks to the 7 of "07 ngày".
    assert not numbers_supported("phí 7 triệu đồng", ["07 Ngày làm việc"]).ok
    assert numbers_supported("phí 7 triệu đồng", ["thu 7.000.000 đồng"]).ok


def test_vnd_answer_is_backed_by_a_unitless_source_amount() -> None:
    assert numbers_supported("mất 160.000 đồng/hộ chiếu", ["160.000/hộ chiếu"]).ok
    assert numbers_supported("mất 160.000 đồng", ["160.000 VNĐ"]).ok
