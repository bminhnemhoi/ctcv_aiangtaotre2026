"""Suite ``dialogue`` — 500 held-out coach dialogues (≤ 2 sentences, action, intent).

Real from E05.
"""

from __future__ import annotations

from ctcv_eval.harness import HarnessConfig
from ctcv_eval.results import SuiteResult
from ctcv_eval.suites import not_ready, sample_count


def run(cfg: HarnessConfig) -> SuiteResult:
    """Skipped in E01; reports the format samples in ``eval/sets/samples/dialog.jsonl``."""
    samples = sample_count(cfg.root, "dialog.jsonl")
    result = not_ready(
        "dialogue", "E05", f"{samples} mẫu định dạng trong eval/sets/samples/dialog.jsonl"
    )
    result.details["format_samples"] = samples
    return result
