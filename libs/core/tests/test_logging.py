from __future__ import annotations

import io
import json
import logging
import re

import pytest

from ctcv_core.logging import (
    DEFAULT_REDACTION,
    JsonFormatter,
    PiiScrubFilter,
    load_pii_patterns,
    request_id_var,
    scrub_pii,
    setup_logging,
)

R = DEFAULT_REDACTION

PII_SAMPLES = [
    (
        "Số CCCD của bác là 079123456789, đừng đọc cho ai.",
        f"Số CCCD của bác là {R}, đừng đọc cho ai.",
    ),
    (
        "Ngân hàng gửi mã OTP là 482913, bác đừng nói cho ai nhé.",
        f"Ngân hàng gửi mã OTP là {R}, bác đừng nói cho ai nhé.",
    ),
    ("OTP: 4821", f"OTP: {R}"),
    ("Mã xác nhận 123456 vừa về máy", f"Mã xác nhận {R} vừa về máy"),
    ("số thẻ 1234 5678 9012 3456", f"số thẻ {R}"),
    ("thẻ 1234-5678-9012-3456 hết hạn", f"thẻ {R} hết hạn"),
    ("gọi 0912345678 hoặc +84912345678", f"gọi {R} hoặc {R}"),
    ("email bac.a+1@example.com.vn", f"email {R}"),
    ("mã 5555 và cccd 012345678901 của cô", f"mã {R} và cccd {R} của cô"),
    ("OTP là 123456789012", f"OTP là {R}"),
]

CLEAN_SAMPLES = [
    "Bác nhập 200.000đ rồi bấm Tiếp tục.",
    "Mã lớp 12 và số 12345",
    "Bác bấm nút xanh có chữ Quét QR nhé.",
    "Số thứ tự 123 tại quầy 4",
]


@pytest.fixture
def patterns():
    return load_pii_patterns()


@pytest.mark.parametrize(("raw", "expected"), PII_SAMPLES)
def test_scrub_pii_samples(patterns, raw: str, expected: str) -> None:
    assert scrub_pii(raw, patterns) == expected


@pytest.mark.parametrize("raw", CLEAN_SAMPLES)
def test_scrub_pii_leaves_clean_text(patterns, raw: str) -> None:
    assert scrub_pii(raw, patterns) == raw


def test_scrub_pii_default_patterns() -> None:
    assert scrub_pii("cccd 079123456789") == f"cccd {R}"


def test_load_pii_patterns_custom_token() -> None:
    cfg = {"redaction_token": "<x>", "pii_patterns": [{"name": "d", "regex": r"\d+"}]}
    pats = load_pii_patterns(cfg)
    assert scrub_pii("a 12 b", pats) == "a <x> b"
    assert all(isinstance(p, re.Pattern) for p, _ in pats)


def _capture(service: str = "test") -> tuple[io.StringIO, logging.Logger]:
    stream = io.StringIO()
    logger = setup_logging(service, level="DEBUG", stream=stream)
    return stream, logger


def _last_json(stream: io.StringIO) -> dict:
    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_json_formatter_fields() -> None:
    stream, logger = _capture("api")
    token = request_id_var.set("req-42")
    try:
        logger.info("xin chào %s", "bác", extra={"session_id": "s1"})
    finally:
        request_id_var.reset(token)
    rec = _last_json(stream)
    assert rec["level"] == "INFO"
    assert rec["logger"] == "api"
    assert rec["service"] == "api"
    assert rec["msg"] == "xin chào bác"
    assert rec["request_id"] == "req-42"
    assert rec["extra"] == {"session_id": "s1"}
    assert rec["ts"].endswith("+00:00")


def test_request_id_defaults_to_null() -> None:
    stream, logger = _capture()
    logger.warning("cảnh báo")
    assert _last_json(stream)["request_id"] is None


def test_scrubs_message_args_and_extra() -> None:
    stream, logger = _capture()
    logger.info("OTP của bác là %s", "482913", extra={"note": "gọi 0912345678", "count": 3})
    rec = _last_json(stream)
    assert rec["msg"] == f"OTP của bác là {R}"
    assert rec["extra"] == {"note": f"gọi {R}", "count": 3}


def test_exception_is_included() -> None:
    stream, logger = _capture()
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("lỗi")
    rec = _last_json(stream)
    assert rec["level"] == "ERROR"
    assert "ValueError: boom" in rec["exc"]


def test_setup_logging_is_idempotent() -> None:
    _capture("a")
    _capture("b")
    root = logging.getLogger()
    ours = [h for h in root.handlers if getattr(h, "_ctcv_handler", False)]
    assert len(ours) == 1


def test_setup_logging_level_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    stream = io.StringIO()
    logger = setup_logging("env", stream=stream)
    logger.info("ẩn")
    logger.warning("hiện")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["msg"] == "hiện"


def test_filter_handles_bad_format_args() -> None:
    flt = PiiScrubFilter(load_pii_patterns())
    record = logging.LogRecord("x", logging.INFO, "f", 1, "cccd %s %s", ("079123456789",), None)
    assert flt.filter(record) is True
    assert R in str(record.msg)


def test_formatter_without_service() -> None:
    record = logging.LogRecord("x", logging.INFO, "f", 1, "m", None, None)
    rec = json.loads(JsonFormatter().format(record))
    assert "service" not in rec
    assert "extra" not in rec
