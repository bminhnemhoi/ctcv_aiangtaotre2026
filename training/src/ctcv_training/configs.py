"""Training configs ``training/configs/<name>.yaml`` validated by ``training/configs/schema.json``.

The YAML files carry the plan §7 defaults (SFT r=16/alpha=32/lr 1e-4/3 epochs/seq 4k/bf16,
DPO 2000 pairs/beta 0.1/1 epoch, AWQ 4-bit + GGUF Q4_K_M, YOLOX-Tiny 50 epochs, optional
ASR LoRA). Models are referenced by their key in ``config/models.yaml`` (``model_key``)
and datasets by their name in ``data/registry/datasets.yaml`` — never by hard-coded ids.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ctcv_core.config import ConfigError, load_config, validate_against_schema
from ctcv_core.paths import REPO_ROOT

CONFIGS_DIRNAME = "configs"
SCHEMA_FILENAME = "schema.json"
CONFIG_NAMES: tuple[str, ...] = ("sft", "dpo", "quantize", "yolox", "asr_lora")
KINDS: tuple[str, ...] = ("sft", "dpo", "quantize", "detector", "asr_lora")


def configs_dir(root: Path | None = None) -> Path:
    """``<root>/training/configs``."""
    return (root or REPO_ROOT) / "training" / CONFIGS_DIRNAME


def load_schema(root: Path | None = None) -> dict[str, Any]:
    """Read ``training/configs/schema.json``."""
    path = configs_dir(root) / SCHEMA_FILENAME
    if not path.is_file():
        raise ConfigError(f"Thiếu schema cấu hình huấn luyện: {path}", {"path": str(path)})
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Thiếu cấu hình huấn luyện: {path}", {"path": str(path)})
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} sai cú pháp YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} phải là bảng khóa–giá trị ở cấp cao nhất.")
    return data


def _model_keys(root: Path | None) -> set[str]:
    return set(load_config("models", root=root)["models"])


def validate_training_config(data: dict[str, Any], *, root: Path | None = None) -> None:
    """Validate ``data`` against the schema; each ``model_key`` must exist in config/models.yaml."""
    validate_against_schema(data, load_schema(root), f"training/{data.get('name', '?')}")
    keys = _model_keys(root)
    referenced = [data["model_key"]] if "model_key" in data else []
    referenced += [t["model_key"] for t in data.get("targets", [])]
    unknown = sorted(set(referenced) - keys)
    if unknown:
        raise ConfigError(
            f"Cấu hình '{data.get('name')}' trỏ tới model_key không có trong config/models.yaml: "
            + ", ".join(unknown),
            {"unknown": unknown},
        )


def load_training_config(name: str, *, root: Path | None = None) -> dict[str, Any]:
    """Load and validate ``training/configs/<name>.yaml``; return the mapping."""
    data = _read_yaml(configs_dir(root) / f"{name}.yaml")
    validate_training_config(data, root=root)
    return data


def load_all(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Every config in :data:`CONFIG_NAMES` keyed by file stem."""
    return {name: load_training_config(name, root=root) for name in CONFIG_NAMES}


def estimated_gpu_hours(configs: dict[str, dict[str, Any]]) -> float:
    """Sum of ``budget.estimated_gpu_hours`` over the given configs (plan §7: ~8–10 h total)."""
    return float(sum(c.get("budget", {}).get("estimated_gpu_hours", 0) for c in configs.values()))
