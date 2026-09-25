from __future__ import annotations

from pathlib import Path

import pytest

from ctcv_core.config import load_config
from ctcv_core.errors import ValidationFailed
from ctcv_speech.settings import (
    ASR_MODEL_ENV,
    DEFAULT_TTS_MAX_TEXT_CHARS,
    MAX_PORT,
    PORT_ENV,
    TTS_CACHE_DIR_ENV,
    TTS_MAX_TEXT_CHARS_ENV,
    TTS_MODEL_ENV,
    SpeechSettings,
    default_tts_cache_dir,
    env_or,
    port_number,
    positive_int,
)


def test_defaults_come_from_config_files():
    models = load_config("models")["models"]
    settings = SpeechSettings.load(env={})
    assert settings.asr_model == models["asr"]["id"]
    assert settings.asr_small_model == models["asr_small"]["id"]
    assert settings.asr_served_by == models["asr"]["served_by"]
    assert settings.asr_confidence_threshold == models["asr"]["confidence_threshold"]
    assert settings.tts_model == models["tts"]["id"]
    assert settings.tts_served_by == models["tts"]["served_by"]
    assert settings.port == load_config("app")["ports"]["speech"]
    assert settings.tts_cache_dir == default_tts_cache_dir()
    assert settings.tts_max_text_chars == DEFAULT_TTS_MAX_TEXT_CHARS
    assert settings.tts_decided is False  # TBD-ADR-002 until the user decides


def test_env_overrides_models_cache_dir_limit_and_port(tmp_path: Path):
    env = {
        ASR_MODEL_ENV: "vinai/PhoWhisper-tiny",
        TTS_MODEL_ENV: "piper/vi_VN-vais1000-medium",
        TTS_CACHE_DIR_ENV: str(tmp_path / "tts"),
        TTS_MAX_TEXT_CHARS_ENV: "300",
        PORT_ENV: "18020",
    }
    settings = SpeechSettings.load(env=env)
    assert settings.asr_model == "vinai/PhoWhisper-tiny"
    assert settings.tts_model == "piper/vi_VN-vais1000-medium"
    assert settings.tts_decided is True
    assert settings.tts_cache_dir == tmp_path / "tts"
    assert settings.tts_max_text_chars == 300
    assert settings.port == 18020


@pytest.mark.parametrize(
    "raw", ["port", "0", "-1", "65536", "70000", "1_000", "+80", "٨٠٢٠", "8020.0", "0x1F"]
)
def test_invalid_port_raises_vietnamese_validation_error(raw: str):
    with pytest.raises(ValidationFailed, match=PORT_ENV) as info:
        SpeechSettings.load(env={PORT_ENV: raw})
    assert info.value.status == 422
    assert "Biến" in info.value.message_vi


def test_port_range_bounds_are_inclusive():
    assert port_number("1", PORT_ENV) == 1
    assert port_number(str(MAX_PORT), PORT_ENV) == MAX_PORT
    assert MAX_PORT == 65535
    with pytest.raises(ValidationFailed, match="1–65535"):
        port_number(str(MAX_PORT + 1), PORT_ENV)


@pytest.mark.parametrize("raw", ["0", "-3", "abc", "1e3", " 7"])
def test_positive_int_rejects_non_decimal_or_non_positive(raw: str):
    with pytest.raises(ValidationFailed, match="K"):
        positive_int(raw, "K")


def test_positive_int_has_no_upper_bound_unless_asked():
    assert positive_int("100000", "K") == 100000
    with pytest.raises(ValidationFailed, match="1–10"):
        positive_int("11", "K", maximum=10)


@pytest.mark.parametrize("raw", ["0", "-1", "many", "1.5"])
def test_invalid_text_limit_raises_vietnamese_validation_error(raw: str):
    with pytest.raises(ValidationFailed, match=TTS_MAX_TEXT_CHARS_ENV):
        SpeechSettings.load(env={TTS_MAX_TEXT_CHARS_ENV: raw})


def test_placeholders_and_blanks_are_ignored():
    env = {
        ASR_MODEL_ENV: "  ",
        TTS_MODEL_ENV: "CHANGE_ME_ADR-002",
        TTS_CACHE_DIR_ENV: "change_me",
        TTS_MAX_TEXT_CHARS_ENV: "",
    }
    settings = SpeechSettings.load(env=env)
    assert settings.asr_model == load_config("models")["models"]["asr"]["id"]
    assert settings.tts_model == "TBD-ADR-002"
    assert settings.tts_cache_dir == default_tts_cache_dir()
    assert settings.tts_max_text_chars == DEFAULT_TTS_MAX_TEXT_CHARS
    assert env_or({"K": "CHANGE_ME"}, "K", "x") == "x"
    assert env_or({"K": "value"}, "K", "x") == "value"
    assert env_or({}, "K", "x") == "x"


def test_load_reads_process_environment(monkeypatch):
    monkeypatch.setenv(ASR_MODEL_ENV, "vinai/PhoWhisper-tiny")
    assert SpeechSettings.load().asr_model == "vinai/PhoWhisper-tiny"
