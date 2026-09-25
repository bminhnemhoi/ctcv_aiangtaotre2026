"""Tool protocol and the ``ToolSpec`` wrapper used by the registry and the router."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Protocol

from pydantic import BaseModel

from ctcv_agent.schemas import SIDE_EFFECTS, SessionContext, SideEffect
from ctcv_agent.tools.backends import Backends

__all__ = ["SIDE_EFFECTS", "SideEffect", "Tool", "ToolSpec"]

ToolRunner = Callable[[Any, SessionContext, Backends], BaseModel]


class Tool(Protocol):
    """Structural interface every tool module implements (module-level attributes)."""

    NAME: str
    SIDE_EFFECT: SideEffect
    Input: type[BaseModel]
    Output: type[BaseModel]

    def run(self, inp: Any, ctx: SessionContext, backends: Backends) -> BaseModel:
        """Execute the tool with validated ``inp`` for the trusted session ``ctx``."""
        ...


@dataclass(frozen=True)
class ToolSpec:
    """Immutable description of one tool, built from its module by :meth:`from_module`."""

    name: str
    side_effect: SideEffect
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    run: ToolRunner
    module: str

    @classmethod
    def from_module(cls, module: ModuleType) -> ToolSpec:
        """Validate that ``module`` implements :class:`Tool` and wrap it.

        Raises:
            TypeError: when an attribute is missing or has the wrong shape (a programming
                error caught at import time, never at request time).
        """
        for attr in ("NAME", "SIDE_EFFECT", "Input", "Output", "run"):
            if not hasattr(module, attr):
                raise TypeError(f"tool module {module.__name__} lacks {attr}")
        name, side_effect = module.NAME, module.SIDE_EFFECT
        if not isinstance(name, str) or not name:
            raise TypeError(f"{module.__name__}.NAME must be a non-empty str")
        if side_effect not in SIDE_EFFECTS:
            raise TypeError(
                f"{module.__name__}.SIDE_EFFECT={side_effect!r} not in {sorted(SIDE_EFFECTS)}"
            )
        for attr in ("Input", "Output"):
            model = getattr(module, attr)
            if not (isinstance(model, type) and issubclass(model, BaseModel)):
                raise TypeError(f"{module.__name__}.{attr} must be a Pydantic model class")
        if not callable(module.run):
            raise TypeError(f"{module.__name__}.run must be callable")
        return cls(
            name=name,
            side_effect=side_effect,
            input_model=module.Input,
            output_model=module.Output,
            run=module.run,
            module=module.__name__,
        )
