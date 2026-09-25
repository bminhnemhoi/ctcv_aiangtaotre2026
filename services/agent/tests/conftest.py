"""Shared fixtures for ctcv-agent tests: fresh backends, contexts, stub planners."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Sequence

import pytest
from pydantic import BaseModel

from ctcv_agent.guardrails import clear_rules_cache
from ctcv_agent.planner import Message, PlannerError
from ctcv_agent.schemas import PlannerOutput, SessionContext, ToolCall
from ctcv_agent.tools.backends import Backends, in_memory_backends, set_default_backends
from ctcv_agent.tools.router import clear_allowed_cache, dispatch
from ctcv_core.config import clear_config_cache


@pytest.fixture(scope="session", autouse=True)
def _no_ollama_num_gpu_override() -> Iterator[None]:
    """Tests read the file config: ``CTCV_OLLAMA_NUM_GPU`` set in the shell must not leak in."""
    saved = os.environ.pop("CTCV_OLLAMA_NUM_GPU", None)
    yield
    if saved is not None:
        os.environ["CTCV_OLLAMA_NUM_GPU"] = saved


@pytest.fixture(autouse=True)
def _fresh_caches() -> Iterator[None]:
    clear_config_cache()
    clear_rules_cache()
    clear_allowed_cache()
    set_default_backends(None)
    yield
    set_default_backends(None)


@pytest.fixture
def backends() -> Backends:
    return in_memory_backends()


@pytest.fixture
def ctx() -> SessionContext:
    return SessionContext(user_id="user-demo", session_id="sess-demo-1")


@pytest.fixture
def router(backends: Backends) -> Callable[[ToolCall, SessionContext], BaseModel]:
    def _route(call: ToolCall, context: SessionContext) -> BaseModel:
        return dispatch(call, context, backends)

    return _route


class ScriptedPlanner:
    """Planner stub returning scripted outputs in order and recording every message list."""

    def __init__(self, outputs: Sequence[PlannerOutput | Exception]) -> None:
        self.outputs = list(outputs)
        self.calls: list[list[Message]] = []

    def complete(self, messages: Sequence[Message]) -> PlannerOutput:
        self.calls.append(list(messages))
        if not self.outputs:
            raise PlannerError("script_exhausted")
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def scripted() -> Callable[..., ScriptedPlanner]:
    def _make(*outputs: PlannerOutput | Exception) -> ScriptedPlanner:
        return ScriptedPlanner(outputs)

    return _make
