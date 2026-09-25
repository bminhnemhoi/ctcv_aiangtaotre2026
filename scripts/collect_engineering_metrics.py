"""Collect model-free engineering metrics into ``eval/reports/engineering.json``.

The competition dossier may only print numbers that were really measured (plan §10). Metrics that
need a model or real users come from ``make eval`` / ``make pilot-report`` (``latest.json``); this
script measures what the repository can prove on any machine: test results, coverage of the core
packages, validator fixtures, contract size, tool whitelist and the guardrail-only red-team run.

Usage: ``uv run python scripts/collect_engineering_metrics.py [--skip-web] [--out PATH]``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "eval" / "reports" / "engineering.json"
TEST_DIRS = (
    "tests", "libs", "services", "sandbox", "drills", "data", "training", "eval", "scripts",
    "deploy", "docs/dossier/build/tests", ".claude/hooks/tests",
)  # fmt: skip
COVERED_PACKAGES = ("ctcv_core", "ctcv_agent", "ctcv_sandbox", "ctcv_drills", "ctcv_api")


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_junit(path: Path) -> dict[str, int]:
    """Sum the ``testsuite`` counters of a JUnit XML report."""
    totals = {"total": 0, "failed": 0, "errors": 0, "skipped": 0}
    for suite in ET.parse(path).getroot().iter("testsuite"):
        totals["total"] += int(suite.get("tests", 0))
        totals["failed"] += int(suite.get("failures", 0))
        totals["errors"] += int(suite.get("errors", 0))
        totals["skipped"] += int(suite.get("skipped", 0))
    totals["passed"] = totals["total"] - totals["failed"] - totals["errors"] - totals["skipped"]
    return totals


def parse_coverage(path: Path) -> dict[str, Any]:
    """Return the total and per-package line coverage from a coverage.py JSON report."""
    data = json.loads(path.read_text(encoding="utf-8"))
    per_package: dict[str, list[int]] = {name: [0, 0] for name in COVERED_PACKAGES}
    for file_name, info in data.get("files", {}).items():
        normalized = file_name.replace("\\", "/")
        for name in COVERED_PACKAGES:
            if f"/{name}/" in normalized:
                per_package[name][0] += info["summary"]["covered_lines"]
                per_package[name][1] += info["summary"]["num_statements"]
    packages = {
        name: round(100 * covered / statements, 1)
        for name, (covered, statements) in per_package.items()
        if statements
    }
    return {"percent": round(data["totals"]["percent_covered"], 1), "packages": packages}


def run_python_tests(workdir: Path) -> tuple[dict[str, int], dict[str, Any]]:
    """Run the whole Python suite once with JUnit and coverage JSON output."""
    junit, cov = workdir / "junit.xml", workdir / "coverage.json"
    dirs = [d for d in TEST_DIRS if (REPO_ROOT / d).exists()]
    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", f"--junitxml={junit}"]
    cmd += [f"--cov={name}" for name in COVERED_PACKAGES]
    cmd += [f"--cov-report=json:{cov}", "--cov-report=", *dirs]
    subprocess.run(cmd, cwd=REPO_ROOT, check=False, capture_output=True, timeout=1800)
    return parse_junit(junit), parse_coverage(cov)


def run_web_tests() -> dict[str, int] | None:
    """Run the vitest suite of apps/web when pnpm and node_modules are present."""
    web = REPO_ROOT / "apps" / "web"
    pnpm = shutil.which("pnpm")
    if pnpm is None or not (web / "node_modules").is_dir():
        return None
    done = subprocess.run(
        [pnpm, "exec", "vitest", "run", "--reporter=json"],
        cwd=web, check=False, capture_output=True, text=True, encoding="utf-8", timeout=900,
    )  # fmt: skip
    start = done.stdout.find("{")
    if start < 0:
        return None
    report = json.loads(done.stdout[start:])
    return {"total": report["numTotalTests"], "passed": report["numPassedTests"]}


def count_json(directory: Path, pattern: str = "*.json") -> int:
    """Count files matching ``pattern`` in ``directory`` (0 when it does not exist)."""
    return len(list(directory.glob(pattern))) if directory.is_dir() else 0


def repo_counts() -> dict[str, Any]:
    """Counts read from the code itself so the dossier never quotes a stale number."""
    from ctcv_agent.tools.registry import TOOL_REGISTRY
    from ctcv_api.main import create_app

    # FastAPI >= 0.141 keeps included routers nested, so count operations from the OpenAPI schema.
    paths = create_app().openapi().get("paths", {})
    api_routes = sorted(
        f"{method.upper()} {path}"
        for path, operations in paths.items()
        if path.startswith("/v1")
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )
    return {
        "sandbox": {
            "scenarios": count_json(REPO_ROOT / "sandbox" / "scenarios"),
            "invalid_fixtures_rejected": count_json(
                REPO_ROOT / "sandbox" / "tests" / "fixtures" / "invalid"
            ),
        },
        "drills": {
            "scenarios": count_json(REPO_ROOT / "drills" / "scenarios"),
            "invalid_fixtures_rejected": count_json(
                REPO_ROOT / "drills" / "tests" / "fixtures" / "invalid"
            ),
        },
        "agent": {"tools": len(TOOL_REGISTRY)},
        "api": {"routes": len(api_routes)},
        "docs": {
            "adr": count_json(REPO_ROOT / "docs" / "decisions", "ADR-0*.md") - 1,  # minus template
            "epics": count_json(REPO_ROOT / "epics", "*.md"),
        },
    }


def redteam_summary() -> dict[str, Any] | None:
    """Copy the guardrail-only red-team result written by ``make redteam`` / the harness."""
    latest = REPO_ROOT / "eval" / "reports" / "latest.json"
    if not latest.is_file():
        return None
    suite = json.loads(latest.read_text(encoding="utf-8")).get("suites", {}).get("redteam", {})
    if suite.get("status") != "ran":
        return None
    metrics = suite.get("metrics", {})
    return {
        "mode": "guardrail-only (không mô hình)",
        "size": int(suite.get("samples", 0)),
        "passed": int(metrics.get("passed", 0)),
        "leaks": int(metrics.get("leaks", 0)),
        "real_actions": int(metrics.get("real_actions", 0)),
    }


def ablation_summary() -> dict[str, Any] | None:
    """Result of ``python -m ctcv_eval.redteam.ablation`` (same attacks, guardrails bypassed)."""
    path = REPO_ROOT / "eval" / "reports" / "redteam-ablation.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def collect(skip_web: bool) -> dict[str, Any]:
    """Run every measurement and return the report dictionary."""
    with tempfile.TemporaryDirectory() as tmp:
        tests, coverage = run_python_tests(Path(tmp))
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "date_vi": datetime.now().strftime("%d/%m/%Y"),
        "python_tests": tests,
        "coverage": coverage,
        "redteam": redteam_summary(),
        "redteam_no_guardrail": ablation_summary(),
        **repo_counts(),
    }
    if not skip_web:
        report["web_tests"] = run_web_tests()
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; writes the JSON report and prints a one-line summary."""
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-web", action="store_true", help="không chạy vitest của apps/web")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    report = collect(args.skip_web)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tests = report["python_tests"]
    print(
        f"Đã ghi {args.out}: {tests['passed']}/{tests['total']} test đạt, "
        f"coverage lõi {report['coverage']['percent']} %."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
