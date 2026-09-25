"""Suite ``audio`` — 10 h of regional speech (WER standard/regional). Real from E04."""

from __future__ import annotations

from ctcv_eval.harness import HarnessConfig
from ctcv_eval.results import SuiteResult
from ctcv_eval.suites import not_ready


def run(cfg: HarnessConfig) -> SuiteResult:
    """Skipped in E01 (Common Voice vi / VIVOS are downloaded at eval time in E04)."""
    del cfg
    return not_ready("audio", "E04")
