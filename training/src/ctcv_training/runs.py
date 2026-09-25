"""Run directories ``training/runs/<YYYY-MM-DD>-<name>/`` (plan §7).

Every training run gets its own folder holding ``config.yaml`` (the exact config used),
``metrics.json`` (status + metrics, updated as the run progresses) and ``MODEL_CARD.md``
(a Vietnamese template the trainer fills in). The folder is git-ignored; the chosen
checkpoint is then declared in ``data/registry/models.yaml``.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ctcv_core.errors import ValidationFailed
from ctcv_core.paths import REPO_ROOT

RUNS_DIRNAME = "runs"
CONFIG_FILE = "config.yaml"
METRICS_FILE = "metrics.json"
CARD_FILE = "MODEL_CARD.md"
LOG_FILE = "train.log"
STATUSES: tuple[str, ...] = ("created", "running", "finished", "failed")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9][a-z0-9-]*)$")

CARD_TEMPLATE = """# Model card — {name}

> Sinh tự động bởi `ctcv_training.runs` ngày {date}. Điền các mục **[điền]** khi run kết thúc;
> checkpoint được chọn ghi vào `data/registry/models.yaml` (brief §9).

## Tổng quan

| Trường | Giá trị |
| --- | --- |
| Tên run | `{run_dir}` |
| Loại | {kind} |
| Model gốc (`config/models.yaml`) | `{model_key}` |
| Bộ dữ liệu (`data/registry/datasets.yaml`) | {datasets} |
| Epic | {epic} |
| Giấy phép | Kế thừa giấy phép model gốc (xem registry); mã nguồn Apache-2.0 |

## Cấu hình

Xem `config.yaml` cùng thư mục (bản sao đúng cấu hình đã dùng).

## Kết quả

- Chỉ số huấn luyện: **[điền]** (ghi trong `metrics.json`).
- Báo cáo eval: **[điền]** (`eval/reports/<ngày>.md`).
- So với model gốc / FP16: **[điền]** (bảng `training/reports/ablation.md`).

## Mục đích sử dụng và giới hạn

- Dùng cho: huấn luyện viên kỹ năng số trong **ứng dụng mô phỏng** của CTCV; không dùng để thao tác
  trên hệ thống thật hay tư vấn pháp lý.
- Giới hạn đã biết: **[điền]** (ví dụ giọng địa phương, câu hỏi ngoài kho hướng dẫn).
- Dữ liệu huấn luyện: chỉ dữ liệu tổng hợp hoặc mở có giấy phép; **không** có dữ liệu pilot thật.

## Kết quả chưa đạt

**[điền]** — ghi trung thực chỗ nào còn yếu (idea §8).
"""


@dataclass(frozen=True)
class RunDir:
    """A run folder and its three well-known files."""

    path: Path
    date: str
    name: str

    @property
    def config_path(self) -> Path:
        """``config.yaml``."""
        return self.path / CONFIG_FILE

    @property
    def metrics_path(self) -> Path:
        """``metrics.json``."""
        return self.path / METRICS_FILE

    @property
    def card_path(self) -> Path:
        """``MODEL_CARD.md``."""
        return self.path / CARD_FILE

    def read_metrics(self) -> dict[str, Any]:
        """Parse ``metrics.json``."""
        return json.loads(self.metrics_path.read_text(encoding="utf-8"))


def runs_dir(root: Path | None = None) -> Path:
    """``<root>/training/runs``."""
    return (root or REPO_ROOT) / "training" / RUNS_DIRNAME


def validate_run_name(name: str) -> str:
    """Accept ``[a-z0-9-]`` names only (they become directory names and registry paths)."""
    if not _NAME_RE.match(name):
        raise ValidationFailed(
            f"Tên run '{name}' không hợp lệ: chỉ chữ thường, số và dấu gạch ngang (≤ 64 ký tự).",
            details={"name": name},
        )
    return name


def _render_card(name: str, run_dir: str, config: Mapping[str, Any], date: str) -> str:
    datasets = [config.get("dataset")] + list(config.get("datasets") or [])
    datasets += [config.get("eval_dataset")]
    listed = ", ".join(f"`{d}`" for d in datasets if d) or "**[điền]**"
    targets = config.get("targets") or []
    model_key = (
        config.get("model_key") or ", ".join(t.get("model_key", "?") for t in targets) or "?"
    )
    return CARD_TEMPLATE.format(
        name=name,
        date=date,
        run_dir=run_dir,
        kind=config.get("kind", "**[điền]**"),
        model_key=model_key,
        datasets=listed,
        epic=config.get("epic", "**[điền]**"),
    )


def create_run(
    name: str,
    config: Mapping[str, Any],
    *,
    root: Path | None = None,
    date: dt.date | None = None,
) -> RunDir:
    """Create ``training/runs/<date>-<name>/`` with config.yaml, metrics.json and MODEL_CARD.md.

    Raises:
        ValidationFailed: when ``name`` is not a slug or the folder already exists (a run
            is never silently overwritten — pick a new name or delete the folder).
    """
    validate_run_name(name)
    stamp = (date or dt.datetime.now(dt.UTC).date()).isoformat()
    path = runs_dir(root) / f"{stamp}-{name}"
    if path.exists():
        raise ValidationFailed(f"Thư mục run đã tồn tại: {path}", details={"path": str(path)})
    path.mkdir(parents=True)
    run = RunDir(path=path, date=stamp, name=name)
    run.config_path.write_text(
        yaml.safe_dump(dict(config), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    payload = {
        "name": name,
        "status": "created",
        "created_at": now,
        "updated_at": now,
        "metrics": {},
    }
    run.metrics_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    run.card_path.write_text(_render_card(name, path.name, config, stamp), encoding="utf-8")
    return run


def update_metrics(
    run: RunDir, metrics: Mapping[str, Any], *, status: str | None = None
) -> dict[str, Any]:
    """Merge ``metrics`` into ``metrics.json`` (and set ``status``); return the new payload."""
    if status is not None and status not in STATUSES:
        raise ValidationFailed(f"Trạng thái run '{status}' không thuộc {STATUSES}")
    data = run.read_metrics()
    data["metrics"] = {**data.get("metrics", {}), **dict(metrics)}
    if status is not None:
        data["status"] = status
    data["updated_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    run.metrics_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


def list_runs(root: Path | None = None) -> list[RunDir]:
    """Every ``<date>-<name>`` folder under ``training/runs``, oldest first."""
    base = runs_dir(root)
    if not base.is_dir():
        return []
    found: list[RunDir] = []
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        match = _DIR_RE.match(child.name)
        if match:
            found.append(RunDir(path=child, date=match.group(1), name=match.group(2)))
    return found
