"""Fixtures for ctcv_data tests: repo root, fixture registries and a temporary repo layout."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ctcv_core.config import find_repo_root

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture
def fake_repo(tmp_path: Path, repo_root: Path) -> Path:
    """A throw-away repo root with the real config/ (schemas) and a fresh data/ tree."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    shutil.copytree(repo_root / "config" / "schemas", root / "config" / "schemas")
    (root / "data").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[tool.uv.workspace]\nmembers = []\n', encoding="utf-8"
    )
    return root


@pytest.fixture
def good_registry(fake_repo: Path) -> Path:
    target = fake_repo / "data" / "registry"
    shutil.copytree(FIXTURES / "registry_good", target)
    (fake_repo / "eval" / "sets").mkdir(parents=True)
    (fake_repo / "eval" / "sets" / "tiny.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
    return target


@pytest.fixture
def bad_registry(fake_repo: Path) -> Path:
    target = fake_repo / "data" / "registry"
    shutil.copytree(FIXTURES / "registry_bad", target)
    return target
