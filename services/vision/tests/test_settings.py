from __future__ import annotations

import pytest

from ctcv_core.config import load_config
from ctcv_core.errors import ValidationFailed
from ctcv_vision.settings import PORT_ENV, SCREEN_TTL_ENV, VLM_MODEL_ENV, VisionSettings, env_or


def test_defaults_come_from_config_files():
    models = load_config("models")["models"]
    app = load_config("app")
    settings = VisionSettings.load(env={})
    assert settings.detector_model == models["ui_detector"]["id"]
    assert settings.detector_served_by == models["ui_detector"]["served_by"]
    assert settings.detector_confidence_threshold == models["ui_detector"]["confidence_threshold"]
    assert settings.vlm_model == models["vlm"]["id"]
    assert settings.vlm_confidence_threshold == models["vlm"]["confidence_threshold"]
    assert settings.vlm_prompt == models["vlm"]["prompt"]
    assert settings.screen_ttl_seconds == app["screen_ttl_seconds"]
    assert settings.port == app["ports"]["vision"]


def test_env_overrides_vlm_ttl_and_port():
    settings = VisionSettings.load(
        env={VLM_MODEL_ENV: "Qwen/Qwen3-VL-8B-Instruct", SCREEN_TTL_ENV: "30", PORT_ENV: "18030"}
    )
    assert settings.vlm_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.screen_ttl_seconds == 30
    assert settings.port == 18030


@pytest.mark.parametrize("raw", ["port", "0"])
def test_invalid_port_raises_vietnamese_validation_error(raw: str):
    with pytest.raises(ValidationFailed, match=PORT_ENV):
        VisionSettings.load(env={PORT_ENV: raw})


def test_placeholders_are_ignored():
    settings = VisionSettings.load(env={VLM_MODEL_ENV: "CHANGE_ME", SCREEN_TTL_ENV: ""})
    assert settings.vlm_model == load_config("models")["models"]["vlm"]["id"]
    assert settings.screen_ttl_seconds == load_config("app")["screen_ttl_seconds"]
    assert env_or({"K": " v "}, "K", "x") == "v"


@pytest.mark.parametrize("raw", ["abc", "0", "-5"])
def test_invalid_ttl_raises_vietnamese_validation_error(raw: str):
    with pytest.raises(ValidationFailed, match=SCREEN_TTL_ENV):
        VisionSettings.load(env={SCREEN_TTL_ENV: raw})


def test_load_reads_process_environment(monkeypatch):
    monkeypatch.setenv(SCREEN_TTL_ENV, "45")
    assert VisionSettings.load().screen_ttl_seconds == 45
