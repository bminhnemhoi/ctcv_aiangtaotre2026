"""Fixtures for ctcv-vision tests."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ctcv_core.config import ENV_PREFIX, clear_config_cache
from ctcv_vision.app import create_app
from ctcv_vision.settings import PORT_ENV, SCREEN_TTL_ENV, VLM_MODEL_ENV, VisionSettings

SERVICE_ENV_KEYS = (VLM_MODEL_ENV, SCREEN_TTL_ENV, PORT_ENV)


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
def settings() -> VisionSettings:
    return VisionSettings.load(env={})


@pytest.fixture
def client(settings: VisionSettings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
