"""Suite ``vision`` — 1.500 sandbox + 200 real screenshots (screen recognition, mAP50).

Real from E08.
"""

from __future__ import annotations

from ctcv_eval.harness import HarnessConfig
from ctcv_eval.results import SuiteResult
from ctcv_eval.suites import not_ready


def run(cfg: HarnessConfig) -> SuiteResult:
    """Skipped in E01 (needs rendered screens and the YOLOX/VLM stack)."""
    del cfg
    return not_ready("vision", "E08")
