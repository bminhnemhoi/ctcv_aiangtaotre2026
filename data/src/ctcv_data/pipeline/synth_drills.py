"""Step stub — implemented in E09; reports CHƯA HIỆN THỰC until then."""

from __future__ import annotations

from ctcv_data.pipeline import PipelineConfig, StepReport


def run(cfg: PipelineConfig) -> StepReport:
    """Return the not-implemented report (E09)."""
    del cfg
    return StepReport.not_implemented("synth_drills")
