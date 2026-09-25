from __future__ import annotations

import pytest

from ctcv_core.config import load_config
from ctcv_vision.redact import (
    DEFAULT_MIN_DIGIT_RUN,
    MaskRegion,
    apply_mask,
    mask_regions,
    redact_digits_in_text,
)

SIZE = (100, 200)  # width, height


def test_pixel_boxes_are_kept_and_serialised():
    regions = mask_regions([{"cls": "otp", "x": 10, "y": 20, "w": 30, "h": 5}], SIZE)
    assert regions == [MaskRegion("otp", 10, 20, 30, 5)]
    assert regions[0].to_dict() == {"cls": "otp", "x": 10, "y": 20, "w": 30, "h": 5}
    assert set(regions[0].to_dict()) == {"cls", "x", "y", "w", "h"}  # never any text field


def test_normalised_boxes_scale_to_the_image():
    regions = mask_regions([{"cls": "card", "bbox": [0.1, 0.25, 0.5, 0.1]}], SIZE)
    assert regions == [MaskRegion("card", 10, 50, 50, 20)]


def test_ambiguous_small_pixel_box_can_be_forced():
    assert mask_regions([(0, 0, 1, 1)], SIZE, normalised=False) == [MaskRegion("pii", 0, 0, 1, 1)]
    assert mask_regions([(0, 0, 1, 1)], SIZE, normalised=True) == [
        MaskRegion("pii", 0, 0, 100, 200)
    ]


def test_boxes_are_clamped_padded_and_empty_ones_dropped():
    regions = mask_regions(
        [
            ("otp", 90, 190, 50, 50),  # spills past the bottom-right corner → clamped
            (-3, -3, 6, 6),  # straddles the top-left corner → clamped
            ("empty", 10, 10, 0, 5),  # zero width → dropped even though padding would widen it
            (200, 200, 5, 5),  # fully outside → dropped
            (-9, -9, 3, 3),  # fully outside even with padding → dropped
        ],
        SIZE,
        padding_px=2,
    )
    assert regions == [MaskRegion("pii", 0, 0, 5, 5), MaskRegion("otp", 88, 188, 12, 12)]


def test_overlapping_boxes_merge_so_no_digit_slips_between():
    regions = mask_regions(
        [("otp", 10, 10, 20, 10), ("otp", 25, 12, 20, 10), ("cccd", 80, 80, 5, 5)], SIZE
    )
    assert regions == [MaskRegion("otp", 10, 10, 35, 12), MaskRegion("cccd", 80, 80, 5, 5)]


def test_merged_regions_of_different_classes_become_mixed():
    regions = mask_regions([("otp", 0, 0, 10, 10), ("card", 5, 5, 10, 10)], SIZE)
    assert regions == [MaskRegion("mixed", 0, 0, 15, 15)]


def test_fractional_pixel_boxes_round_outwards():
    assert mask_regions([(10.4, 10.6, 5.2, 5.2)], SIZE, normalised=False) == [
        MaskRegion("pii", 10, 10, 6, 6)
    ]


@pytest.mark.parametrize(
    ("boxes", "size", "padding"),
    [
        ([(1, 2, 3)], SIZE, 0),
        ([{"x": 1, "y": 2}], SIZE, 0),
        ([{"cls": "otp", "bbox": "0.1,0.2,0.3,0.4"}], SIZE, 0),
        ([{"bbox": [1, 2, 3]}], SIZE, 0),
        ([], (0, 10), 0),
        ([], SIZE, -1),
    ],
)
def test_invalid_input_raises_value_error(boxes, size, padding):
    with pytest.raises(ValueError):
        mask_regions(boxes, size, padding_px=padding)


def test_apply_mask_paints_only_the_regions():
    grid = [[0] * 6 for _ in range(4)]
    masked = apply_mask(grid, [MaskRegion("otp", 1, 1, 2, 2), MaskRegion("x", 5, 3, 9, 9)], 1)
    assert masked[0] == [0, 0, 0, 0, 0, 0]
    assert masked[1] == [0, 1, 1, 0, 0, 0]
    assert masked[2] == [0, 1, 1, 0, 0, 0]
    assert masked[3] == [0, 0, 0, 0, 0, 1]
    assert grid[1] == [0, 0, 0, 0, 0, 0]  # input untouched


def test_redact_digits_uses_guardrails_token_and_pii_patterns():
    token = load_config("guardrails")["redaction_token"]
    text = (
        "Số CCCD 079123456789, OTP là 482913, gọi 0912345678, "
        "mã đơn 12345, thẻ 1234 5678 9012 3456."
    )
    out = redact_digits_in_text(text)
    assert out == f"Số CCCD {token}, OTP là {token}, gọi {token}, mã đơn {token}, thẻ {token}."
    assert DEFAULT_MIN_DIGIT_RUN == 4


def test_redact_digits_keeps_short_numbers_and_amounts():
    token = load_config("guardrails")["redaction_token"]
    assert redact_digits_in_text("Bác nhập 200.000đ rồi bấm Tiếp tục, quầy số 4.") == (
        f"Bác nhập {token}đ rồi bấm Tiếp tục, quầy số 4."
    )
    assert redact_digits_in_text("Mã lớp 12 và số 123", min_digits=4) == "Mã lớp 12 và số 123"
    assert redact_digits_in_text("năm 2026", min_digits=5) == "năm 2026"
    assert redact_digits_in_text("năm 2026", token="***") == "năm ***"


def test_redact_digits_rejects_bad_threshold():
    with pytest.raises(ValueError):
        redact_digits_in_text("x", min_digits=0)
