"""Training configs: schema validity, plan §7 defaults, model_key resolution, budget sums."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from ctcv_core.config import ConfigError
from ctcv_training.configs import (
    CONFIG_NAMES,
    configs_dir,
    estimated_gpu_hours,
    load_all,
    load_schema,
    load_training_config,
    validate_training_config,
)


def test_schema_is_valid_2020_12(repo_root: Path) -> None:
    Draft202012Validator.check_schema(load_schema(repo_root))


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_every_config_validates(repo_root: Path, name: str) -> None:
    cfg = load_training_config(name, root=repo_root)
    assert cfg["version"] == 1 and cfg["name"] and cfg["epic"].startswith("E")
    assert cfg["budget"]["estimated_gpu_hours"] <= 20
    assert cfg["budget"]["estimated_api_vnd"] <= 500_000


def test_sft_defaults_match_plan_section_7(repo_root: Path) -> None:
    sft = load_training_config("sft", root=repo_root)
    assert sft["model_key"] == "planner"
    assert sft["lora"]["r"] == 16 and sft["lora"]["alpha"] == 32
    assert sft["train"]["learning_rate"] == pytest.approx(1e-4)
    assert sft["train"]["epochs"] == 3
    assert sft["train"]["max_seq_len"] == 4096
    assert sft["train"]["precision"] == "bf16"
    assert sft["train"]["gradient_checkpointing"] is True
    assert sft["stop"] == {"metric": "eval_loss", "mode": "min", "patience": 2}
    assert sft["dataset"] == "coach-sft-v1"


def test_dpo_quantize_yolox_asr_defaults(repo_root: Path) -> None:
    dpo = load_training_config("dpo", root=repo_root)
    assert dpo["dpo"]["pairs"] == 2000 and dpo["dpo"]["beta"] == pytest.approx(0.1)
    assert dpo["dpo"]["epochs"] == 1 and dpo["stop"]["threshold"] == pytest.approx(0.5)
    quant = load_training_config("quantize", root=repo_root)
    by_key = {t["model_key"]: t for t in quant["targets"]}
    assert by_key["planner"]["method"] == "awq" and by_key["planner"]["bits"] == 4
    assert by_key["planner_small"]["method"] == "gguf"
    assert by_key["planner_small"]["quant_type"] == "Q4_K_M"
    assert quant["stop"]["max_allowed"] == 2
    yolox = load_training_config("yolox", root=repo_root)
    assert yolox["detector"]["arch"] == "yolox-tiny" and yolox["detector"]["epochs"] == 50
    assert yolox["detector"]["images"] == 20000 and yolox["export"]["format"] == "onnx"
    assert yolox["stop"]["threshold"] == pytest.approx(0.85)
    asr = load_training_config("asr_lora", root=repo_root)
    assert asr["optional"] is True and asr["model_key"] == "asr"
    assert asr["audio"]["consent_required"] is True
    assert (asr["audio"]["min_hours"], asr["audio"]["max_hours"]) == (5, 10)
    assert asr["stop"]["threshold"] == 3


def test_model_keys_resolve_and_planner_small_is_2b(repo_root: Path) -> None:
    models = yaml.safe_load((repo_root / "config" / "models.yaml").read_text(encoding="utf-8"))
    assert models["models"]["planner_small"]["id"] == "Qwen/Qwen3.5-2B"  # D8
    for cfg in load_all(repo_root).values():
        keys = [cfg["model_key"]] if "model_key" in cfg else []
        keys += [t["model_key"] for t in cfg.get("targets", [])]
        assert keys and all(k in models["models"] for k in keys)


def test_total_estimate_fits_one_night(repo_root: Path) -> None:
    total = estimated_gpu_hours(load_all(repo_root))
    assert 6 <= total <= 10  # plan §7: ~8–10 giờ tổng trên 1 GPU 24 GB


def test_no_raw_model_ids_in_configs(repo_root: Path) -> None:
    for path in configs_dir(repo_root).glob("*.yaml"):
        body = "\n".join(
            line.split("#", 1)[0] for line in path.read_text(encoding="utf-8").splitlines()
        )
        assert "Qwen/" not in body and "vinai/" not in body and "huggingface.co" not in body, path


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda c: c["lora"].update(r=0), "lora/r"),
        (lambda c: c.pop("stop"), "stop"),
        (lambda c: c["budget"].update(estimated_gpu_hours=21), "estimated_gpu_hours"),
        (lambda c: c.update(kind="rlhf"), "kind"),
        (lambda c: c.update(extra=1), "extra"),
        (lambda c: c["train"].update(precision="int4"), "precision"),
    ],
)
def test_invalid_sft_is_rejected(repo_root: Path, mutate, needle: str) -> None:
    cfg = copy.deepcopy(load_training_config("sft", root=repo_root))
    mutate(cfg)
    with pytest.raises(ConfigError, match=needle):
        validate_training_config(cfg, root=repo_root)


def test_unknown_model_key_is_rejected(repo_root: Path) -> None:
    cfg = copy.deepcopy(load_training_config("sft", root=repo_root))
    cfg["model_key"] = "gpt_4"
    with pytest.raises(ConfigError, match="model_key"):
        validate_training_config(cfg, root=repo_root)


def test_missing_config_raises(repo_root: Path) -> None:
    with pytest.raises(ConfigError, match="Thiếu"):
        load_training_config("nope", root=repo_root)


def test_schema_file_is_json(repo_root: Path) -> None:
    raw = json.loads((configs_dir(repo_root) / "schema.json").read_text(encoding="utf-8"))
    assert set(raw["properties"]["kind"]["enum"]) == {
        "sft",
        "dpo",
        "quantize",
        "detector",
        "asr_lora",
    }
