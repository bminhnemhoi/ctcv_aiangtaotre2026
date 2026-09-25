"""Run directories: creation, files, model card template, metrics updates, listing."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

from ctcv_core.errors import ValidationFailed
from ctcv_training.runs import RunDir, create_run, list_runs, runs_dir, update_metrics

CONFIG = {
    "version": 1,
    "kind": "sft",
    "name": "planner-sft",
    "epic": "E07",
    "model_key": "planner",
    "dataset": "coach-sft-v1",
    "eval_dataset": "eval-dialogue-v1",
    "lora": {"r": 16, "alpha": 32},
}


def test_create_run_writes_three_files(tmp_path: Path) -> None:
    run = create_run("planner-sft", CONFIG, root=tmp_path, date=dt.date(2026, 9, 18))
    assert run.path == tmp_path / "training" / "runs" / "2026-09-18-planner-sft"
    assert run.date == "2026-09-18" and run.name == "planner-sft"
    assert yaml.safe_load(run.config_path.read_text(encoding="utf-8")) == CONFIG
    metrics = run.read_metrics()
    assert metrics["status"] == "created" and metrics["metrics"] == {}
    assert metrics["created_at"] == metrics["updated_at"]
    card = run.card_path.read_text(encoding="utf-8")
    assert card.startswith("# Model card — planner-sft")
    for needle in (
        "`planner`",
        "`coach-sft-v1`",
        "`eval-dialogue-v1`",
        "E07",
        "[điền]",
        "mô phỏng",
    ):
        assert needle in card, needle


def test_create_run_refuses_overwrite_and_bad_names(tmp_path: Path) -> None:
    create_run("dup", CONFIG, root=tmp_path, date=dt.date(2026, 9, 18))
    with pytest.raises(ValidationFailed, match="đã tồn tại"):
        create_run("dup", CONFIG, root=tmp_path, date=dt.date(2026, 9, 18))
    for bad in ("Planner", "a b", "-x", "", "x" * 65):
        with pytest.raises(ValidationFailed, match="không hợp lệ"):
            create_run(bad, CONFIG, root=tmp_path)


def test_quantize_card_lists_targets(tmp_path: Path) -> None:
    cfg = {
        "kind": "quantize",
        "epic": "E07",
        "targets": [{"model_key": "planner"}, {"model_key": "planner_small"}],
    }
    run = create_run("quant", cfg, root=tmp_path, date=dt.date(2026, 9, 18))
    assert "`planner, planner_small`" in run.card_path.read_text(encoding="utf-8")


def test_update_metrics_merges_and_sets_status(tmp_path: Path) -> None:
    run = create_run("dpo", CONFIG, root=tmp_path, date=dt.date(2026, 9, 18))
    update_metrics(run, {"eval_loss": 0.9}, status="running")
    data = update_metrics(run, {"reward_margin": 0.6}, status="finished")
    assert data["status"] == "finished"
    assert data["metrics"] == {"eval_loss": 0.9, "reward_margin": 0.6}
    assert json.loads(run.metrics_path.read_text(encoding="utf-8")) == data
    with pytest.raises(ValidationFailed, match="Trạng thái"):
        update_metrics(run, {}, status="done")


def test_list_runs_orders_and_ignores_strays(tmp_path: Path) -> None:
    assert list_runs(tmp_path) == []
    create_run("b", CONFIG, root=tmp_path, date=dt.date(2026, 9, 19))
    create_run("a", CONFIG, root=tmp_path, date=dt.date(2026, 9, 18))
    (runs_dir(tmp_path) / "not-a-run").mkdir()
    (runs_dir(tmp_path) / ".gitkeep").write_text("", encoding="utf-8")
    runs = list_runs(tmp_path)
    assert [r.name for r in runs] == ["a", "b"]
    assert all(isinstance(r, RunDir) for r in runs)


def test_real_runs_dir_is_gitkept(repo_root: Path) -> None:
    assert (runs_dir(repo_root) / ".gitkeep").is_file()
    assert (repo_root / "training" / "reports" / ".gitkeep").is_file()
