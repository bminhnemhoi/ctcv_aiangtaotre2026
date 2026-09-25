"""Repo-root fixtures shared by tests/config and tests/invariants."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from ctcv_core.config import ENV_PREFIX, clear_config_cache, find_repo_root

CONFIG_NAMES = ("app", "models", "tools", "guardrails", "eval")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture(scope="session")
def config_dir(repo_root: Path) -> Path:
    return repo_root / "config"


@pytest.fixture(scope="session")
def load_yaml(config_dir: Path) -> Callable[[str], Any]:
    def _load(name: str) -> Any:
        return yaml.safe_load((config_dir / f"{name}.yaml").read_text(encoding="utf-8"))

    return _load


@pytest.fixture(scope="session")
def load_schema(config_dir: Path) -> Callable[[str], dict[str, Any]]:
    def _load(name: str) -> dict[str, Any]:
        path = config_dir / "schemas" / f"{name}.schema.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def tmp_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str, str], None]]:
    """Set CTCV_* env vars for one test; clears the config cache before and after."""
    for key in list(os.environ):
        if key.startswith(f"{ENV_PREFIX}_"):
            monkeypatch.delenv(key, raising=False)
    clear_config_cache()

    def _set(key: str, value: str) -> None:
        monkeypatch.setenv(key, value)
        clear_config_cache()

    yield _set
    clear_config_cache()
