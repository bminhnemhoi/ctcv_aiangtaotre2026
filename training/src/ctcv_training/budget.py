"""GPU-hour and API-spend budget gate (plan §4, brief §11/D22).

This module is **standard library only** and imports nothing from the workspace, so the
Claude Code hook (``.claude/hooks/budget.py``) and CI can import it without the project
virtualenv. The single source of truth is ``training/budget.json``::

    {
      "gpu_hours_total_limit": 300,   "gpu_hours_per_job_limit": 20,
      "api_budget_vnd": 2000000,      "api_per_task_limit_vnd": 500000,
      "spent": {"gpu_hours": 0, "api_vnd": 0}, "updated_at": "..."
    }

``check(job_estimate_hours, api_vnd)`` answers "may this job start?" with a
:class:`Decision`; ``record_spend`` accumulates what a finished job actually used.
CLI: ``python -m ctcv_training.budget --hours 3 [--api-vnd 0] [--record]``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BUDGET_FILENAME = "budget.json"
DEFAULT_GPU_TOTAL_HOURS = 300.0
DEFAULT_GPU_PER_JOB_HOURS = 20.0
DEFAULT_API_BUDGET_VND = 2_000_000.0
DEFAULT_API_PER_TASK_VND = 500_000.0
# The Claude Code hook reads this alias; both keys must agree when present.
API_BUDGET_ALIAS = "api_total_limit_vnd"
EXIT_OK, EXIT_BLOCKED, EXIT_USAGE = 0, 1, 2


class BudgetError(ValueError):
    """``training/budget.json`` is missing, malformed or internally inconsistent."""


@dataclass(frozen=True)
class Limits:
    """Ceilings declared in ``budget.json`` (per job/task and cumulative)."""

    gpu_hours_total: float
    gpu_hours_per_job: float
    api_budget_vnd: float
    api_per_task_vnd: float


@dataclass(frozen=True)
class Decision:
    """Outcome of :func:`check`: ``allowed`` plus Vietnamese ``reasons`` when blocked."""

    allowed: bool
    job_gpu_hours: float
    job_api_vnd: float
    gpu_hours_remaining: float
    api_vnd_remaining: float
    reasons: list[str] = field(default_factory=list)

    def message(self) -> str:
        """One Vietnamese line for the console or the hook."""
        if self.allowed:
            return (
                f"Trong hạn mức: job {self.job_gpu_hours:g} giờ GPU / {self.job_api_vnd:,.0f} đ; "
                f"còn lại {self.gpu_hours_remaining:g} giờ GPU và {self.api_vnd_remaining:,.0f} đ."
            )
        return "VƯỢT NGÂN SÁCH — hỏi người dùng trước khi chạy: " + "; ".join(self.reasons)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form (used by the CLI ``--json`` flag)."""
        return {
            "allowed": self.allowed,
            "job_gpu_hours": self.job_gpu_hours,
            "job_api_vnd": self.job_api_vnd,
            "gpu_hours_remaining": self.gpu_hours_remaining,
            "api_vnd_remaining": self.api_vnd_remaining,
            "reasons": list(self.reasons),
        }


def default_budget_path(root: Path | None = None) -> Path:
    """``<root>/training/budget.json``; ``root`` defaults to the repository root."""
    base = root if root is not None else Path(__file__).resolve().parents[3]
    return base / "training" / BUDGET_FILENAME


def now_iso() -> str:
    """UTC timestamp with second precision (ISO-8601)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BudgetError(f"trường '{label}' phải là số, nhận được {value!r}")
    if value < 0:
        raise BudgetError(f"trường '{label}' không được âm ({value})")
    return float(value)


def load_budget(path: Path) -> dict[str, Any]:
    """Read and sanity-check ``budget.json``; raise :class:`BudgetError` on any problem."""
    if not path.is_file():
        raise BudgetError(f"thiếu file ngân sách {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BudgetError(f"không đọc được {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise BudgetError(f"{path.name} phải là một object JSON")
    if not isinstance(data.get("spent", {}), dict):
        raise BudgetError("trường 'spent' phải là object {gpu_hours, api_vnd}")
    api_budget = data.get("api_budget_vnd", data.get(API_BUDGET_ALIAS))
    alias = data.get(API_BUDGET_ALIAS)
    if api_budget is not None and alias is not None and api_budget != alias:
        raise BudgetError(f"'api_budget_vnd' ({api_budget}) khác '{API_BUDGET_ALIAS}' ({alias})")
    return data


def limits_of(budget: dict[str, Any]) -> Limits:
    """Extract the four ceilings (defaults from plan §4 when a key is absent)."""
    api_budget = budget.get("api_budget_vnd", budget.get(API_BUDGET_ALIAS, DEFAULT_API_BUDGET_VND))
    return Limits(
        gpu_hours_total=_number(
            budget.get("gpu_hours_total_limit", DEFAULT_GPU_TOTAL_HOURS), "gpu_hours_total_limit"
        ),
        gpu_hours_per_job=_number(
            budget.get("gpu_hours_per_job_limit", DEFAULT_GPU_PER_JOB_HOURS),
            "gpu_hours_per_job_limit",
        ),
        api_budget_vnd=_number(api_budget, "api_budget_vnd"),
        api_per_task_vnd=_number(
            budget.get("api_per_task_limit_vnd", DEFAULT_API_PER_TASK_VND), "api_per_task_limit_vnd"
        ),
    )


def spent_of(budget: dict[str, Any]) -> tuple[float, float]:
    """``(gpu_hours_spent, api_vnd_spent)`` from the ``spent`` block."""
    spent = budget.get("spent") or {}
    return _number(spent.get("gpu_hours", 0), "spent.gpu_hours"), _number(
        spent.get("api_vnd", 0), "spent.api_vnd"
    )


def evaluate(budget: dict[str, Any], job_estimate_hours: float, api_vnd: float = 0.0) -> Decision:
    """Pure decision on an already-loaded budget mapping (no I/O)."""
    hours = _number(job_estimate_hours, "job_estimate_hours")
    vnd = _number(api_vnd, "api_vnd")
    lim = limits_of(budget)
    gpu_spent, api_spent = spent_of(budget)
    reasons: list[str] = []
    if hours > lim.gpu_hours_per_job:
        reasons.append(f"job dự kiến {hours:g} giờ GPU > hạn mức {lim.gpu_hours_per_job:g} giờ/job")
    if vnd > lim.api_per_task_vnd:
        reasons.append(f"API dự kiến {vnd:,.0f} đ > hạn mức {lim.api_per_task_vnd:,.0f} đ/tác vụ")
    if gpu_spent + hours > lim.gpu_hours_total:
        reasons.append(
            f"tổng GPU {gpu_spent + hours:g} giờ > tổng hạn mức {lim.gpu_hours_total:g} giờ"
        )
    if api_spent + vnd > lim.api_budget_vnd:
        reasons.append(
            f"tổng API {api_spent + vnd:,.0f} đ > tổng hạn mức {lim.api_budget_vnd:,.0f} đ"
        )
    return Decision(
        allowed=not reasons,
        job_gpu_hours=hours,
        job_api_vnd=vnd,
        gpu_hours_remaining=max(lim.gpu_hours_total - gpu_spent - hours, 0.0),
        api_vnd_remaining=max(lim.api_budget_vnd - api_spent - vnd, 0.0),
        reasons=reasons,
    )


def check(job_estimate_hours: float, api_vnd: float = 0.0, *, path: Path | None = None) -> Decision:
    """Decide whether a job may start, reading ``training/budget.json`` (fail closed).

    A missing or malformed budget file yields a blocked :class:`Decision` whose reason
    names the problem, so a broken file can never silently allow a job.
    """
    try:
        return evaluate(load_budget(path or default_budget_path()), job_estimate_hours, api_vnd)
    except BudgetError as exc:
        return Decision(
            allowed=False,
            job_gpu_hours=float(job_estimate_hours),
            job_api_vnd=float(api_vnd),
            gpu_hours_remaining=0.0,
            api_vnd_remaining=0.0,
            reasons=[f"training/budget.json lỗi ({exc}) — sửa file rồi chạy lại"],
        )


def record_spend(
    gpu_hours: float, api_vnd: float = 0.0, *, path: Path | None = None, job_name: str = ""
) -> dict[str, Any]:
    """Add what a finished job used to ``spent`` and stamp ``updated_at``; return the new data."""
    target = path or default_budget_path()
    data = load_budget(target)
    gpu_spent, api_spent = spent_of(data)
    data["spent"] = {
        "gpu_hours": round(gpu_spent + _number(gpu_hours, "gpu_hours"), 3),
        "api_vnd": round(api_spent + _number(api_vnd, "api_vnd")),
    }
    data["updated_at"] = now_iso()
    if job_name:
        data["last_job"] = {"name": job_name, "gpu_hours": gpu_hours, "api_vnd": api_vnd}
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def build_parser() -> argparse.ArgumentParser:
    """CLI parser: ``--hours`` (required), ``--api-vnd``, ``--budget``, ``--record``, ``--json``."""
    parser = argparse.ArgumentParser(
        prog="python -m ctcv_training.budget",
        description="Kiểm tra (hoặc ghi nhận) ngân sách GPU/API trước và sau một job huấn luyện.",
    )
    parser.add_argument("--hours", type=float, required=True, help="giờ GPU dự kiến (hoặc đã dùng)")
    parser.add_argument("--api-vnd", type=float, default=0.0, help="chi phí API dự kiến (đồng)")
    parser.add_argument("--budget", type=Path, default=None, help="đường dẫn budget.json thay thế")
    parser.add_argument("--name", default="", help="tên job (ghi vào last_job khi --record)")
    parser.add_argument(
        "--record", action="store_true", help="cộng --hours/--api-vnd vào spent (sau khi job xong)"
    )
    parser.add_argument("--json", action="store_true", help="in kết quả dạng JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: exit 0 when allowed, 1 when blocked, 2 on usage/file errors."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.hours < 0 or args.api_vnd < 0:
        print("Lỗi: --hours và --api-vnd không được âm.", file=sys.stderr)
        return EXIT_USAGE
    if args.record:
        try:
            data = record_spend(args.hours, args.api_vnd, path=args.budget, job_name=args.name)
        except BudgetError as exc:
            print(f"Lỗi: {exc}", file=sys.stderr)
            return EXIT_USAGE
        spent = data["spent"]
        print(f"Đã ghi: tổng {spent['gpu_hours']:g} giờ GPU, {spent['api_vnd']:,.0f} đ API.")
        return EXIT_OK
    decision = check(args.hours, args.api_vnd, path=args.budget)
    print(json.dumps(decision.to_dict(), ensure_ascii=False) if args.json else decision.message())
    return EXIT_OK if decision.allowed else EXIT_BLOCKED


if __name__ == "__main__":
    sys.exit(main())
