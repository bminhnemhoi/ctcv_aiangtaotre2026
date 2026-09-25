"""build_eval_sets: deterministic TTHC questions from procedure records (ADR-007 C8)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from ctcv_agent.rag.query import fold_accents
from ctcv_agent.rag.types import ProcedureRecord
from ctcv_core.config import validate_against_schema
from ctcv_data.pipeline import PipelineConfig
from ctcv_data.pipeline import build_eval_sets as step

AGENT_RECORDS = Path("services/agent/tests/fixtures/tthc/records")
SCHEMA = Path("eval/sets/samples/qa_tthc.schema.json")
OUT = Path("eval/sets/samples/qa_tthc.jsonl")


def _schema(root: Path) -> dict:
    return json.loads((root / SCHEMA).read_text(encoding="utf-8"))


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def layout(fake_repo: Path, repo_root: Path) -> Path:
    """Fake repo with the 3 agent fixture records and the real C8 schema."""
    records = fake_repo / "data" / "clean" / "tthc" / "records"
    shutil.copytree(repo_root / AGENT_RECORDS, records)
    (fake_repo / SCHEMA).parent.mkdir(parents=True)
    shutil.copy(repo_root / SCHEMA, fake_repo / SCHEMA)
    return fake_repo


def _clone_records(root: Path, count: int) -> None:
    """Replace the records by ``count`` copies of 1.004222 with distinct ids."""
    records = root / "data" / "clean" / "tthc" / "records"
    base = ProcedureRecord.load(records / "1.004222.json").model_dump(mode="json")
    shutil.rmtree(records)
    records.mkdir()
    for i in range(count):
        data = json.loads(json.dumps(base))
        data["procedure_id"] = data["ma_thu_tuc"] = f"9.{i:06d}"
        data["ten"] = f"Đăng ký thường trú loại {i}"
        data["meta"]["matt"] = str(50000 + i)
        (records / f"9.{i:06d}.json").write_text(json.dumps(data, ensure_ascii=False), "utf-8")


def test_skipped_without_records(fake_repo: Path) -> None:
    report = step.run(PipelineConfig(root=fake_repo))
    assert report.status == "skipped"
    assert not (fake_repo / OUT).exists()


def test_rows_follow_schema_and_contract(layout: Path) -> None:
    report = step.run(PipelineConfig(root=layout))
    assert report.status == "ok", report.message
    rows = _read(layout / OUT)
    schema = _schema(layout)
    for row in rows:
        validate_against_schema(row, schema, "qa_tthc")
        assert row["source"] == "generated:tthc-template/1"
        assert row["expect"] == "answer" and row["kind"] in {"field", "no_diacritics"}
        assert not re.search(r"\d{9,}", row["question"])
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    per_proc: dict[str, int] = {}
    for row in rows:
        per_proc[row["gold_procedure_id"]] = per_proc.get(row["gold_procedure_id"], 0) + 1
    assert set(per_proc) == {"1.004194", "1.004222", "2.000200"}
    assert max(per_proc.values()) <= 2
    assert report.details["rows"] == len(rows)


def test_expected_values_copied_from_structured_fields(layout: Path) -> None:
    step.run(PipelineConfig(root=layout))
    rows = {(r["gold_procedure_id"], r["gold_intent"]): r for r in _read(layout / OUT)}
    assert rows[("1.004222", "phi_le_phi")]["expected_values"] == ["20.000", "10.000"]
    assert rows[("1.004222", "thoi_han")]["expected_values"] == ["07 Ngày làm việc"]
    # no amount in 1.004194 → no fee question; documents use the form code
    assert ("1.004194", "phi_le_phi") not in rows
    assert rows[("1.004194", "thoi_han")]["expected_values"] == ["03 Ngày làm việc"]


def test_split_follows_gold_procedure_hash(layout: Path) -> None:
    step.run(PipelineConfig(root=layout))
    for row in _read(layout / OUT):
        digest = int(hashlib.sha256(row["gold_procedure_id"].encode("utf-8")).hexdigest(), 16)
        assert row["split"] == ("dev" if digest % 10 < 3 else "test")


def test_output_is_deterministic(layout: Path) -> None:
    step.run(PipelineConfig(root=layout))
    first = (layout / OUT).read_bytes()
    step.run(PipelineConfig(root=layout))
    assert (layout / OUT).read_bytes() == first


def test_flagged_fee_records_get_no_fee_question(layout: Path) -> None:
    report_path = layout / "data" / "clean" / "tthc" / "normalize_report.json"
    warning = "26360: phi_bat_thuong: có mức phí > 10,000,000 đồng — cần người kiểm tra nguồn"
    report_path.write_text(json.dumps({"warnings": [warning]}), encoding="utf-8")
    report = step.run(PipelineConfig(root=layout))
    rows = _read(layout / OUT)
    assert not [r for r in rows if r["gold_intent"] == "phi_le_phi"]
    assert report.details["fee_flagged_dropped"] == 1


def test_cap_no_diacritics_share_and_template_variety(layout: Path) -> None:
    _clone_records(layout, 80)
    step.run(PipelineConfig(root=layout))
    rows = _read(layout / OUT)
    assert len(rows) == step.MAX_QUESTIONS
    folded = [r for r in rows if r["kind"] == "no_diacritics"]
    assert len(folded) == step.MAX_QUESTIONS // 10
    assert all(fold_accents(r["question"]) == r["question"] for r in folded)
    assert all(fold_accents(r["question"]) != r["question"] for r in rows if r["kind"] == "field")
    openings = {r["question"].split()[0] for r in rows if r["gold_intent"] == "phi_le_phi"}
    assert len(openings) >= 3
    assert {r["split"] for r in rows} == {"dev", "test"}


def test_committed_set_is_valid_and_large_enough(repo_root: Path) -> None:
    rows = _read(repo_root / OUT)
    schema = _schema(repo_root)
    assert len(rows) >= 100
    for row in rows:
        validate_against_schema(row, schema, "qa_tthc")
