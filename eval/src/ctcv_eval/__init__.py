"""ctcv-eval: the evaluation side of CTCV (plan §7 ``make eval``, §6 red-team, §7 load test).

* :mod:`ctcv_eval.harness` — six suites (qa, dialogue, vision, audio, redteam, loadtest)
  compared with the accept/block thresholds of ``config/eval.yaml``; writes
  ``eval/reports/<date>.md`` and exits 1 only when a suite that actually ran breaches a
  block threshold.
* :mod:`ctcv_eval.redteam` — model-free red-team runner over ``eval/redteam/scenarios.jsonl``
  through ``ctcv_agent`` (guardrails + router + quarantine); part of ``make check``.
* :mod:`ctcv_eval.pilot` — ``make pilot-kit`` / ``make pilot-report`` entry point (E01: schema
  validation of the pilot CSV only).
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
