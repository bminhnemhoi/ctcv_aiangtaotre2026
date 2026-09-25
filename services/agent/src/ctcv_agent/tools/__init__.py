"""The closed tool set of the coach (brief §7, config/tools.yaml).

One module per tool; each declares ``NAME``, ``SIDE_EFFECT`` (``none``/``sandbox``/``log``),
Pydantic ``Input``/``Output`` models and ``run(inp, ctx, backends)``. The registry
(:mod:`ctcv_agent.tools.registry`) wraps them in a read-only mapping and the router
(:mod:`ctcv_agent.tools.router`) is the only caller.

No tool module may import ``httpx``, ``requests``, ``subprocess``, ``socket`` or use
``os.system`` — see ``tests/invariants/test_tool_whitelist.py``. Adding a tool is a
mandatory stop point (plan §6): ask the user, then update ``config/tools.yaml``.
"""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    """Expose ``TOOL_REGISTRY`` lazily so importing a tool module never imports all of them."""
    if name == "TOOL_REGISTRY":
        from ctcv_agent.tools.registry import TOOL_REGISTRY

        return TOOL_REGISTRY
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
