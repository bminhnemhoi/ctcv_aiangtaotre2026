"""The "− guardrail" ablation must show that guardrails, not luck, stop the attacks."""

from __future__ import annotations

from ctcv_eval.redteam import default_scenarios_path, load_scenarios, run_scenarios, summarize
from ctcv_eval.redteam.ablation import run_ablation


def test_guardrails_block_attacks_that_succeed_without_them() -> None:
    scenarios = load_scenarios(default_scenarios_path())
    guarded = summarize(run_scenarios(scenarios))
    unguarded = summarize(run_ablation(scenarios))
    assert guarded.failed == 0
    assert unguarded.failed > guarded.failed
    assert unguarded.leaks > 0
