"""Suite registry and runner of ``make eval`` (plan §7: six suites, accept/block thresholds).

Each suite is a module ``ctcv_eval.suites.<name>`` exposing ``run(cfg) -> SuiteResult``.
E01: ``redteam`` runs for real through :mod:`ctcv_eval.redteam`; the other five report
``skipped`` until their evaluation sets exist (qa E03, dialogue E05, vision E08, audio E04,
loadtest E11). ``run_harness`` returns exit code 1 only when a suite that *ran* breaches a
block threshold — a skipped suite never fails CI.
"""

from __future__ import annotations

import datetime as dt
import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ctcv_core.paths import REPO_ROOT
from ctcv_eval.results import (
    MetricRow,
    SuiteResult,
    evaluate_rows,
    has_block,
    render_report,
    reports_dir,
    write_latest_json,
    write_report,
)
from ctcv_eval.thresholds import SUITE_NAMES, SuiteThresholds, load_thresholds

SUITE_ORDER: tuple[str, ...] = SUITE_NAMES
SUITE_ALIASES: dict[str, str] = {"dialog": "dialogue", "red-team": "redteam", "load": "loadtest"}


@dataclass(slots=True)
class HarnessConfig:
    """Options shared by every suite."""

    root: Path = REPO_ROOT
    quick: bool = False
    report_dir: Path | None = None
    scenarios_path: Path | None = None
    date: dt.date | None = None
    write_reports: bool = True

    def reports(self) -> Path:
        """``eval/reports`` (or the override)."""
        return self.report_dir or reports_dir(self.root)

    def today(self) -> dt.date:
        """Report date (UTC today unless fixed for tests)."""
        return self.date or dt.datetime.now(dt.UTC).date()


@dataclass(slots=True)
class HarnessRun:
    """Everything one harness invocation produced."""

    results: list[SuiteResult]
    rows: list[MetricRow]
    thresholds: dict[str, SuiteThresholds]
    report_path: Path | None = None
    latest_path: Path | None = None
    skipped: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """1 when a ran suite breaches a block threshold, else 0."""
        return 1 if has_block(self.rows) else 0


SuiteFn = Callable[[HarnessConfig], SuiteResult]


def resolve_suite(name: str) -> str:
    """Canonical suite name (``dialog`` → ``dialogue``); unknown names raise ``KeyError``."""
    canonical = SUITE_ALIASES.get(name, name)
    if canonical not in SUITE_ORDER:
        raise KeyError(name)
    return canonical


def get_suite(name: str) -> SuiteFn:
    """Import ``ctcv_eval.suites.<name>`` and return its ``run``."""
    module = importlib.import_module(f"ctcv_eval.suites.{resolve_suite(name)}")
    return module.run


def run_harness(cfg: HarnessConfig, suites: list[str] | None = None) -> HarnessRun:
    """Run ``suites`` (default: all six in order), compare with thresholds, write reports."""
    names = [resolve_suite(s) for s in suites] if suites else list(SUITE_ORDER)
    thresholds = load_thresholds(cfg.root)
    results = [get_suite(name)(cfg) for name in names]
    rows = evaluate_rows(results, thresholds)
    run = HarnessRun(
        results=results,
        rows=rows,
        thresholds=thresholds,
        skipped=[r.name for r in results if not r.ran],
    )
    if cfg.write_reports:
        text = render_report(results, rows, thresholds, quick=cfg.quick)
        run.report_path = write_report(cfg.reports(), text, cfg.today())
        run.latest_path = write_latest_json(cfg.reports(), results, rows, quick=cfg.quick)
    return run
