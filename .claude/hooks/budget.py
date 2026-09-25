"""Training/API budget gate (brief §11, D22) — used by ``guard.py`` and standalone.

Reads ``training/budget.json`` (a default file is created when missing) and
reports when the next job's estimate exceeds ``gpu_hours_per_job_limit`` (20 h),
``api_per_task_limit_vnd`` (500.000 đ) or the cumulative limits. Standalone use:
``python budget.py`` prints the verdict and exits 2 when over budget.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from _common import block, eprint, now_iso, project_dir, read_stdin_json, utf8_streams

BUDGET_FILE = Path("training") / "budget.json"
DEFAULT_BUDGET: dict[str, Any] = {
    "version": 1,
    "gpu_hours_per_job_limit": 20,
    "api_per_task_limit_vnd": 500000,
    "gpu_hours_total_limit": 300,
    "api_total_limit_vnd": 2000000,
    "next_job": {"name": "", "estimated_gpu_hours": 0, "estimated_api_vnd": 0},
    "spent": {"gpu_hours": 0, "api_vnd": 0},
    "updated_at": "",
    "note": (
        "ml-trainer/data-engineer cập nhật next_job (ước tính) trước khi chạy make train/data; "
        "hook guard chặn lệnh khi ước tính vượt hạn mức (plan §6: hỏi người dùng)."
    ),
}


class BudgetError(Exception):
    """Raised when ``training/budget.json`` cannot be read or is malformed."""


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BudgetError(f"trường {label} phải là số, nhận được {value!r}")
    return float(value)


def load_budget(root: Path) -> dict[str, Any]:
    """Load the budget file, creating the default one when it does not exist."""
    path = root / BUDGET_FILE
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(DEFAULT_BUDGET, updated_at=now_iso())
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BudgetError(f"không đọc được {BUDGET_FILE.as_posix()}: {exc}") from exc
    if not isinstance(data, dict):
        raise BudgetError(f"{BUDGET_FILE.as_posix()} phải là object JSON")
    return data


def evaluate(budget: dict[str, Any]) -> list[str]:
    """Return Vietnamese problem descriptions (empty when within budget)."""
    job = budget.get("next_job") or {}
    spent = budget.get("spent") or {}
    if not isinstance(job, dict) or not isinstance(spent, dict):
        raise BudgetError("next_job và spent phải là object")
    gpu_job = _number(job.get("estimated_gpu_hours", 0), "next_job.estimated_gpu_hours")
    api_job = _number(job.get("estimated_api_vnd", 0), "next_job.estimated_api_vnd")
    gpu_spent = _number(spent.get("gpu_hours", 0), "spent.gpu_hours")
    api_spent = _number(spent.get("api_vnd", 0), "spent.api_vnd")
    gpu_limit = _number(budget.get("gpu_hours_per_job_limit", 20), "gpu_hours_per_job_limit")
    api_limit = _number(budget.get("api_per_task_limit_vnd", 500000), "api_per_task_limit_vnd")
    gpu_total = _number(budget.get("gpu_hours_total_limit", 300), "gpu_hours_total_limit")
    api_total = _number(budget.get("api_total_limit_vnd", 2000000), "api_total_limit_vnd")
    problems: list[str] = []
    if gpu_job > gpu_limit:
        problems.append(f"job dự kiến {gpu_job:g} giờ GPU > hạn mức {gpu_limit:g} giờ/job")
    if api_job > api_limit:
        problems.append(f"chi phí API dự kiến {api_job:,.0f} đ > hạn mức {api_limit:,.0f} đ/tác vụ")
    if gpu_spent + gpu_job > gpu_total:
        problems.append(f"tổng GPU {gpu_spent + gpu_job:g} giờ > tổng hạn mức {gpu_total:g} giờ")
    if api_spent + api_job > api_total:
        problems.append(f"tổng API {api_spent + api_job:,.0f} đ > tổng hạn mức {api_total:,.0f} đ")
    return problems


def check(root: Path) -> list[str]:
    """Load + evaluate; malformed files count as a problem (fail closed)."""
    try:
        return evaluate(load_budget(root))
    except BudgetError as exc:
        return [f"training/budget.json lỗi ({exc}) — sửa file rồi chạy lại"]


def main() -> int:
    """Standalone entry point (stdin JSON optional)."""
    utf8_streams()
    data, _ = read_stdin_json()
    problems = check(project_dir(data))
    if problems:
        block("vượt ngân sách huấn luyện — hỏi người dùng trước: " + "; ".join(problems))
    eprint("budget: trong hạn mức (training/budget.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
