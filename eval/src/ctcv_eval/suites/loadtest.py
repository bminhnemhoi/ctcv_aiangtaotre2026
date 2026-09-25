"""Suite ``loadtest`` — 50 concurrent users via k6 (p95, error rate). Runs on staging from E11.

The k6 script lives in ``eval/loadtest/k6.js``; this suite only reports its presence in E01.
Later epics parse ``k6 run --summary-export`` output into the ``p95_latency_s`` and
``error_rate`` metrics of ``config/eval.yaml``.
"""

from __future__ import annotations

from ctcv_eval.harness import HarnessConfig
from ctcv_eval.results import SuiteResult
from ctcv_eval.suites import not_ready

K6_SCRIPT = ("eval", "loadtest", "k6.js")


def run(cfg: HarnessConfig) -> SuiteResult:
    """Skipped in E01 (needs a staging deployment and the k6 binary)."""
    script = cfg.root.joinpath(*K6_SCRIPT)
    extra = "kịch bản k6 sẵn sàng, chạy từ máy GPU/staging" if script.is_file() else "thiếu k6.js"
    result = not_ready("loadtest", "E11", extra)
    result.details["k6_script"] = script.is_file()
    return result
