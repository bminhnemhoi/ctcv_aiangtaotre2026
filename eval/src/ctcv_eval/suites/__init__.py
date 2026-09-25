"""The six evaluation suites (plan §7). Each module exposes ``run(cfg) -> SuiteResult``.

Skipped suites use :func:`not_ready` so the reason text is uniform:
``chưa có tập đánh giá (E0X)`` — the harness never counts them as failures.
"""

from __future__ import annotations

from pathlib import Path

from ctcv_eval.results import SuiteResult

SAMPLES_DIRNAME = ("eval", "sets", "samples")


def not_ready(name: str, epic: str, extra: str = "") -> SuiteResult:
    """A suite whose evaluation set lands in ``epic``."""
    reason = f"chưa có tập đánh giá ({epic})" + (f" — {extra}" if extra else "")
    return SuiteResult.skipped(name, reason, epic=epic)


def sample_count(root: Path, filename: str) -> int:
    """Number of non-blank JSONL lines in ``eval/sets/samples/<filename>`` (0 when absent)."""
    path = root.joinpath(*SAMPLES_DIRNAME, filename)
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
