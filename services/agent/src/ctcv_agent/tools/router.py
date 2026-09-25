"""Tool router: the only path from a planner's ``ToolCall`` to code (brief §7).

``dispatch`` runs a tool only when its name is in :data:`TOOL_REGISTRY` **and** in
``config/tools.yaml``, the declared side effect agrees, and the arguments validate
against the tool's ``Input`` model (unknown keys such as ``user_id`` are rejected).
Anything else raises :class:`ToolNotAllowed`; nothing else is ever executed.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ValidationError

from ctcv_agent.schemas import SessionContext, ToolCall
from ctcv_agent.tools.backends import Backends, default_backends
from ctcv_agent.tools.base import ToolSpec
from ctcv_agent.tools.registry import TOOL_REGISTRY
from ctcv_core.config import load_config
from ctcv_core.errors import AppError


class ToolNotAllowed(AppError):  # noqa: N818 — name fixed by the E01 brief (§7)
    """The planner asked for a tool or arguments the whitelist does not permit."""

    def __init__(self, name: str, reason: str, details: Mapping[str, Any] | None = None) -> None:
        """Build a 403 ``TOOL_NOT_ALLOWED`` error with a Vietnamese message."""
        super().__init__(
            "TOOL_NOT_ALLOWED",
            "Trợ lý không được phép làm việc này, cháu sẽ nhờ tình nguyện viên giúp bác nhé.",
            403,
            {"tool": name, "reason": reason, **(details or {})},
        )
        self.tool = name
        self.reason = reason


@lru_cache(maxsize=1)
def allowed_tools() -> Mapping[str, Mapping[str, Any]]:
    """Tools declared in ``config/tools.yaml`` keyed by name."""
    return {entry["name"]: entry for entry in load_config("tools")["tools"]}


def clear_allowed_cache() -> None:
    """Forget the cached whitelist (tests that swap the config call this)."""
    allowed_tools.cache_clear()


def resolve(name: str) -> ToolSpec:
    """Return the spec for ``name`` when registry and config both allow it."""
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        raise ToolNotAllowed(name, "unknown_tool")
    entry = allowed_tools().get(name)
    if entry is None:
        raise ToolNotAllowed(name, "not_in_config")
    if entry["side_effect"] != spec.side_effect:
        raise ToolNotAllowed(name, "side_effect_mismatch")
    return spec


def validate_args(spec: ToolSpec, args: Mapping[str, Any]) -> BaseModel:
    """Validate ``args`` with the tool's ``Input`` model; report locations, never values."""
    try:
        return spec.input_model.model_validate(dict(args))
    except ValidationError as exc:
        errors = [
            {"loc": ".".join(str(p) for p in e["loc"]), "type": e["type"]} for e in exc.errors()
        ]
        raise ToolNotAllowed(spec.name, "invalid_args", {"errors": errors}) from None


def dispatch(call: ToolCall, ctx: SessionContext, backends: Backends | None = None) -> BaseModel:
    """Run ``call`` for the trusted ``ctx`` and return the tool's ``Output`` model."""
    spec = resolve(call.name)
    inp = validate_args(spec, call.args)
    return spec.run(inp, ctx, backends or default_backends())
