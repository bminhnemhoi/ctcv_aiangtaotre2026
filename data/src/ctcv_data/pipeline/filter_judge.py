"""Step stub — implemented in E06; reports CHƯA HIỆN THỰC until then."""

from __future__ import annotations

from ctcv_data.pipeline import PipelineConfig, StepReport


def run(cfg: PipelineConfig) -> StepReport:
    """Return the not-implemented report (E06)."""
    del cfg
    return StepReport.not_implemented("filter_judge")
