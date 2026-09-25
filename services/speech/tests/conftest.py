"""Fixtures for ctcv-speech tests."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ctcv_core.config import ENV_PREFIX, clear_config_cache
from ctcv_speech.app import create_app
from ctcv_speech.settings import (
    ASR_MODEL_ENV,
    PORT_ENV,
    TTS_CACHE_DIR_ENV,
    TTS_MAX_TEXT_CHARS_ENV,
    TTS_MODEL_ENV,
    SpeechSettings,
)

SERVICE_ENV_KEYS = (
    ASR_MODEL_ENV,
    TTS_MODEL_ENV,
    TTS_CACHE_DIR_ENV,
    TTS_MAX_TEXT_CHARS_ENV,
    PORT_ENV,
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip CTCV_* and service env vars and clear the config cache around every test."""
    for key in list(os.environ):
        if key.startswith(f"{ENV_PREFIX}_") or key in SERVICE_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture
def settings() -> SpeechSettings:
    return SpeechSettings.load(env={})


@pytest.fixture
def client(settings: SpeechSettings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
