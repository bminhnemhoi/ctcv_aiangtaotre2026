"""Accept/block thresholds from ``config/eval.yaml`` (plan §7 ``make eval`` table).

Semantics (also documented in the YAML header)::

    direction: higher → ĐẠT if value >= accept; CHẶN if value <  block; else CẢNH BÁO
    direction: lower  → ĐẠT if value <= accept; CHẶN if value >  block; else CẢNH BÁO

Only these thresholds decide the harness exit code; nothing here is hard-coded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ctcv_core.config import load_config

Verdict = Literal["ĐẠT", "CẢNH BÁO", "CHẶN"]
PASS: Verdict = "ĐẠT"
WARN: Verdict = "CẢNH BÁO"
BLOCK: Verdict = "CHẶN"
SUITE_NAMES: tuple[str, ...] = ("qa", "dialogue", "vision", "audio", "redteam", "loadtest")


@dataclass(frozen=True)
class Metric:
    """One metric of a suite with its unit, direction and the two thresholds."""

    suite: str
    name: str
    unit: str
    direction: Literal["higher", "lower"]
    accept: float
    block: float

    def verdict(self, value: float) -> Verdict:
        """Compare ``value`` with the thresholds (see module docstring)."""
        if self.direction == "higher":
            if value >= self.accept:
                return PASS
            return BLOCK if value < self.block else WARN
        if value <= self.accept:
            return PASS
        return BLOCK if value > self.block else WARN

    def format(self, value: float) -> str:
        """Render ``value`` with its unit (``95%``, ``0.85``, ``3``, ``2.5 s``)."""
        return format_value(value, self.unit)


@dataclass(frozen=True)
class SuiteThresholds:
    """Thresholds and sizing of one suite."""

    name: str
    title: str
    quick_size: int
    size: int | None
    metrics: Mapping[str, Metric]


def format_value(value: float, unit: str) -> str:
    """Human form of a metric value for the Markdown table."""
    if unit == "percent":
        return f"{value:g}%"
    if unit == "seconds":
        return f"{value:g} s"
    if unit == "count":
        return f"{int(value)}" if float(value).is_integer() else f"{value:g}"
    return f"{value:g}"


def _suite(name: str, raw: Mapping[str, Any]) -> SuiteThresholds:
    metrics = {
        key: Metric(
            suite=name,
            name=key,
            unit=str(m["unit"]),
            direction=m["direction"],
            accept=float(m["accept"]),
            block=float(m["block"]),
        )
        for key, m in raw["metrics"].items()
    }
    return SuiteThresholds(
        name=name,
        title=str(raw.get("title", name)),
        quick_size=int(raw.get("quick_size", 0)),
        size=int(raw["size"]) if "size" in raw else None,
        metrics=metrics,
    )


def load_thresholds(root: Path | None = None) -> dict[str, SuiteThresholds]:
    """Load and validate ``config/eval.yaml``; return ``{suite_name: SuiteThresholds}``."""
    cfg = load_config("eval", root=root)
    return {name: _suite(name, raw) for name, raw in cfg["suites"].items()}


def quick_total(root: Path | None = None) -> int:
    """``quick.total_samples`` — the CI sample budget for ``make eval QUICK=1``."""
    return int(load_config("eval", root=root)["quick"]["total_samples"])
