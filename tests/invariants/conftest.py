"""Fixtures for the invariant tests: fresh config, guardrail and router caches per test."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ctcv_agent.guardrails import clear_rules_cache
from ctcv_agent.tools.backends import set_default_backends
from ctcv_agent.tools.router import clear_allowed_cache
from ctcv_core.config import clear_config_cache


@pytest.fixture(autouse=True)
def _fresh_agent_caches() -> Iterator[None]:
    clear_config_cache()
    clear_rules_cache()
    clear_allowed_cache()
    set_default_backends(None)
    yield
    set_default_backends(None)
