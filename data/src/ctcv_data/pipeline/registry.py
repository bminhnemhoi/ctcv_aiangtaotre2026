"""Step 9 — registry: validate ``data/registry/*.yaml``, hash artefacts, write REPORT.md."""

from __future__ import annotations

from ctcv_data.pipeline import PipelineConfig, StepReport
from ctcv_data.registry import run_registry


def run(cfg: PipelineConfig) -> StepReport:
    """Validate both registries against their schemas and report hash status."""
    result = run_registry(cfg.root, cfg.registry_dir, update_hashes=cfg.update_hashes)
    details = {
        "datasets": len(result.datasets),
        "models": len(result.models),
        "problems": result.problems,
        "warnings": result.warnings,
        "hashes": {h.name: h.status for h in result.hash_checks},
    }
    outputs = [str(result.report_path)] if result.report_path else []
    if not result.ok:
        message = f"{len(result.problems)} lỗi: " + "; ".join(result.problems[:3])
        return StepReport("registry", "failed", message, details, outputs)
    message = (
        f"{len(result.datasets)} bộ dữ liệu, {len(result.models)} mô hình hợp lệ; "
        f"{len(result.warnings)} cảnh báo (sha256 pending/thiếu file)."
    )
    return StepReport("registry", "ok", message, details, outputs)
