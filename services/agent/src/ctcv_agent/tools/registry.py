"""``TOOL_REGISTRY``: the read-only mapping of the eight tools (brief §7).

The mapping is a :class:`types.MappingProxyType`, so nothing can add a tool at runtime.
Adding one is a mandatory stop point: ask the user, update ``config/tools.yaml``, add the
module here and let ``tests/invariants/test_tool_whitelist.py`` confirm both lists agree.
"""

from __future__ import annotations

from types import MappingProxyType

from ctcv_agent.tools import (
    escalate_to_volunteer,
    get_session_state,
    grade_drill,
    log_progress,
    next_step,
    search_guides,
    start_drill,
    verify_citation,
)
from ctcv_agent.tools.base import ToolSpec

_MODULES = (
    get_session_state,
    next_step,
    search_guides,
    verify_citation,
    start_drill,
    grade_drill,
    log_progress,
    escalate_to_volunteer,
)

TOOL_REGISTRY: MappingProxyType[str, ToolSpec] = MappingProxyType(
    {spec.name: spec for spec in (ToolSpec.from_module(m) for m in _MODULES)}
)


def tool_names() -> frozenset[str]:
    """Names of every registered tool."""
    return frozenset(TOOL_REGISTRY)
