"""Step stub — implemented in E08; reports CHƯA HIỆN THỰC until then."""

from __future__ import annotations

from ctcv_data.pipeline import PipelineConfig, StepReport


def run(cfg: PipelineConfig) -> StepReport:
    """Return the not-implemented report (E08)."""
    del cfg
    return StepReport.not_implemented("render_ui")
