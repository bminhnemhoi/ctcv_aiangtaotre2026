"""Fixtures for ctcv_training tests: repo root, temporary budget files, temporary run roots."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from ctcv_core.config import find_repo_root


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return find_repo_root()


@pytest.fixture
def budget_file(tmp_path: Path) -> Callable[..., Path]:
    """Write a budget.json with the plan §4 limits and the given ``spent``; return its path."""

    def _make(gpu_spent: float = 0, api_spent: float = 0, **overrides: object) -> Path:
        data: dict[str, object] = {
            "version": 1,
            "gpu_hours_total_limit": 300,
            "gpu_hours_per_job_limit": 20,
            "api_budget_vnd": 2000000,
            "api_total_limit_vnd": 2000000,
            "api_per_task_limit_vnd": 500000,
            "next_job": {"name": "", "estimated_gpu_hours": 0, "estimated_api_vnd": 0},
            "spent": {"gpu_hours": gpu_spent, "api_vnd": api_spent},
            "updated_at": "2026-09-18T00:00:00+00:00",
        }
        data.update(overrides)
        path = tmp_path / "budget.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    return _make
