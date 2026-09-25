"""Suite ``redteam`` — delegates to :mod:`ctcv_eval.redteam` (model-free, guardrails only).

Metrics map onto ``config/eval.yaml: suites.redteam`` (``leaks``, ``real_actions``, both
accept 0 / block 0) plus informational counts (``passed``, ``failed``, ``total``).
"""

from __future__ import annotations

from ctcv_eval.harness import HarnessConfig
from ctcv_eval.redteam import default_scenarios_path, load_scenarios, run_scenarios, summarize
from ctcv_eval.results import SuiteResult
from ctcv_eval.thresholds import load_thresholds


def run(cfg: HarnessConfig) -> SuiteResult:
    """Run every scenario (``--quick``: the first ``quick_size`` of them) and count failures."""
    path = cfg.scenarios_path or default_scenarios_path(cfg.root)
    scenarios = load_scenarios(path)
    if cfg.quick:
        quick_size = load_thresholds(cfg.root)["redteam"].quick_size
        scenarios = scenarios[:quick_size]
    outcomes = run_scenarios(scenarios, root=cfg.root)
    summary = summarize(outcomes)
    return SuiteResult(
        name="redteam",
        metrics={
            "leaks": float(summary.leaks),
            "real_actions": float(summary.real_actions),
            "failed": float(summary.failed),
            "passed": float(summary.passed),
        },
        samples=summary.total,
        details={"scenarios": str(path), "by_category": summary.by_category},
    )
