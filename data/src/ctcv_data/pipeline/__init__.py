"""Step registry for ``python -m ctcv_data.pipeline`` (plan §7: nine steps + registry).

Every step is a module ``ctcv_data.pipeline.<step>`` exposing ``run(cfg) -> StepReport``.
Steps that a later epic implements return ``StepReport.not_implemented`` so ``make data``
stays runnable (and exits 0) from E01 onwards.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ctcv_core.paths import REPO_ROOT

Status = Literal["ok", "skipped", "failed"]

STEP_ORDER: tuple[str, ...] = (
    "crawl",
    "normalize",
    "chunk_embed",
    "synth_scenarios",
    "render_ui",
    "synth_dialogues",
    "filter_judge",
    "synth_drills",
    "build_eval_sets",
    "registry",
)
STEP_EPICS: dict[str, str] = {
    "crawl": "E03",
    "normalize": "E03",
    "chunk_embed": "E03",
    "synth_scenarios": "E06",
    "render_ui": "E08",
    "synth_dialogues": "E06",
    "filter_judge": "E06",
    "synth_drills": "E09",
    "build_eval_sets": "E06",
    "registry": "E01",
}
NOT_IMPLEMENTED_PREFIX = "CHƯA HIỆN THỰC"


@dataclass(slots=True)
class PipelineConfig:
    """Options shared by every step."""

    root: Path = REPO_ROOT
    online: bool = False
    raw_dir: Path | None = None
    registry_dir: Path | None = None
    update_hashes: bool = False
    clean_dir: Path | None = None

    def raw(self) -> Path:
        """``data/raw`` (or the override)."""
        return self.raw_dir or self.root / "data" / "raw"

    def clean(self) -> Path:
        """``data/clean`` (or the override)."""
        return self.clean_dir or self.root / "data" / "clean"


@dataclass(slots=True)
class StepReport:
    """What a step did; ``exit_code`` is 1 only for ``failed``."""

    step: str
    status: Status
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """0 for ok/skipped, 1 for failed."""
        return 1 if self.status == "failed" else 0

    @classmethod
    def not_implemented(cls, step: str) -> StepReport:
        """Report for a step owned by a later epic."""
        epic = STEP_EPICS.get(step, "E0X")
        return cls(step, "skipped", f"{NOT_IMPLEMENTED_PREFIX} — {epic} ({step})", {"epic": epic})


StepFn = Callable[[PipelineConfig], StepReport]


def get_step(name: str) -> StepFn:
    """Import ``ctcv_data.pipeline.<name>`` and return its ``run``; unknown names raise."""
    if name not in STEP_ORDER:
        raise KeyError(name)
    module = importlib.import_module(f"ctcv_data.pipeline.{name}")
    return module.run


def run_steps(names: list[str], cfg: PipelineConfig) -> list[StepReport]:
    """Run ``names`` in order, stopping after the first failure."""
    reports: list[StepReport] = []
    for name in names:
        report = get_step(name)(cfg)
        reports.append(report)
        if report.status == "failed":
            break
    return reports
