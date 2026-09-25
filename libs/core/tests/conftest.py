"""Shared fixtures for ctcv-core tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ctcv_core.config import ENV_PREFIX, REPO_ROOT_ENV, clear_config_cache, find_repo_root

MINIMAL_ROOT_PYPROJECT = '[project]\nname = "tmp"\n\n[tool.uv.workspace]\nmembers = []\n'


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear cached configs and strip CTCV_* env vars around every test."""
    for key in list(os.environ):
        if key.startswith(f"{ENV_PREFIX}_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    """A throw-away workspace root with config/ and config/schemas/ directories."""
    (tmp_path / "pyproject.toml").write_text(MINIMAL_ROOT_PYPROJECT, encoding="utf-8")
    (tmp_path / "config" / "schemas").mkdir(parents=True)
    return tmp_path
