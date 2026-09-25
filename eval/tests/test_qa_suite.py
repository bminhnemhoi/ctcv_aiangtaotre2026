"""Suite ``qa`` over TTHC: loading, metrics names, details, ablation report (no model)."""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

from ctcv_agent.ask import AnswerEngine
from ctcv_agent.compose import ComposeOutput
from ctcv_agent.rag.fake import FakeKnowledgeBase
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import Chunk, KnowledgeBaseNotReady, ProcedureRecord
from ctcv_core.config import ConfigError, find_repo_root
from ctcv_eval.harness import HarnessConfig
from ctcv_eval.results import SuiteResult, write_latest_json
from ctcv_eval.suites import qa
from ctcv_eval.tthc_metrics import METRIC_NAMES

REPO = find_repo_root()
RECORDS = REPO / "services" / "agent" / "tests" / "fixtures" / "tthc" / "records"
SCHEMA = REPO / "eval" / "sets" / "samples" / "qa_tthc.schema.json"
DENSE = {"1.004222": 0.62, "2.000200": 0.66, "1.004194": 0.6}
FEE_CHUNK = "tthc-1.004222-phi_le_phi-0"
GOOD_FEE = (
    "Bác nộp hồ sơ trực tiếp thì mất 20.000 đồng mỗi lần đăng ký, "
    "còn nộp trực tuyến thì mất 10.000 đồng mỗi lần."
)
MADE_UP_TIME = "Đăng ký thường trú mất 30 ngày làm việc."


class RuleComposer:
    """Answers the fee question well, invents a time limit, is unsure otherwise."""

    hosts_contacted: list[str] = []

    def compose(self, question: str, chunks: Sequence[Chunk]) -> ComposeOutput:
        if "tiền" in question:
            return ComposeOutput(GOOD_FEE, (FEE_CHUNK,), True, None, 1.0)
        if "bao lâu" in question:
            return ComposeOutput(MADE_UP_TIME, (), True, None, 1.0)
        return ComposeOutput(None, (), True, None, 1.0)


def row(iid: str, split: str, kind: str, question: str, gold: str | None, values: list[str]):
    return {
        "id": iid,
        "split": split,
        "kind": kind,
        "question": question,
        "expect": "answer" if gold else "refuse_or_escalate",
        "gold_procedure_id": gold,
        "gold_intent": None,
        "expected_values": values,
        "source": "handwritten:qa-tester",
        "notes": "",
    }


ROWS = [
    row("t-1", "test", "field", "Đăng ký thường trú mất bao nhiêu tiền?", "1.004222",
        ["20.000", "10.000"]),
    row("t-2", "test", "field", "Đăng ký thường trú mất bao lâu?", "1.004222",
        ["07 Ngày làm việc"]),
    row("t-3", "test", "colloquial", "Làm căn cước cho cháu 14 tuổi cần mang giấy tờ gì?",
        "2.000200", []),
    row("t-4", "test", "out_of_kb", "Thủ tục đăng ký kết hôn cần những gì?", None, []),
    row("t-5", "test", "sensitive",
        "Có người xưng công an gọi xin mã OTP, tôi có đọc không?", None, []),
    row("d-1", "dev", "field", "Đăng ký tạm trú cần giấy tờ gì?", "1.004194", []),
]  # fmt: skip


@pytest.fixture(scope="module")
def settings() -> RagSettings:
    return load_rag_settings()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(REPO / "config", tmp_path / "config")
    samples = tmp_path / "eval" / "sets" / "samples"
    samples.mkdir(parents=True)
    shutil.copy(SCHEMA, samples / SCHEMA.name)
    lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS)
    (samples / "qa_tthc_handwritten.jsonl").write_text(lines, encoding="utf-8")
    return tmp_path


@pytest.fixture
def factory(settings: RagSettings):
    records = [ProcedureRecord.load(p) for p in sorted(RECORDS.glob("*.json"))]
    built: list[str | None] = []

    def _factory(mode: str | None, kb: object | None) -> AnswerEngine:
        built.append(mode)
        base = kb or FakeKnowledgeBase(records, DENSE, settings=settings)
        composer = None if mode == "template_only" else RuleComposer()
        return AnswerEngine(base, composer, settings, mode=mode or "llm_verified")

    _factory.built = built  # type: ignore[attr-defined]
    return _factory


def _cfg(root: Path, **kw: object) -> HarnessConfig:
    return HarnessConfig(root=root, report_dir=root / "reports", **kw)


def test_runs_on_test_split_with_c8_metric_names(root: Path, factory) -> None:
    result = qa.run(_cfg(root), engine_factory=factory)
    assert result.ran and result.name == "qa" and result.samples == 5
    assert set(result.metrics) - {"answer_accuracy_text_only"} <= set(METRIC_NAMES)
    assert set(METRIC_NAMES) - set(result.metrics) == set(result.details["undefined_metrics"])
    assert "answer_accuracy_text_only" in result.metrics
    assert result.metrics["refusal_accuracy"] == 100.0
    assert factory.built == [None, "template_only"]


def test_details_follow_c8(root: Path, factory) -> None:
    details = qa.run(_cfg(root), engine_factory=factory).details
    assert {"kb", "split_sizes", "per_kind", "network_hosts", "composer_failures", "mode"} <= set(
        details
    )
    assert details["split_sizes"] == {"dev": 1, "test": 5}
    assert details["per_kind"]["sensitive"] == {"n": 1, "ok": 1}
    assert details["network_hosts"] == [] and details["mode"] == "llm_verified"
    assert details["kb"]["procedures"] == 3
    json.dumps(details)  # serialisable for latest.json


def test_ablation_report_has_three_modes_from_one_run(root: Path, factory) -> None:
    qa.run(_cfg(root), engine_factory=factory)
    data = json.loads((root / "reports" / "ablation-tthc.json").read_text(encoding="utf-8"))
    assert set(data["modes"]) == {"template_only", "llm_unverified", "llm_verified"}
    assert data["split"] == "test" and data["n_in_scope"] == 5
    for mode in data["modes"].values():
        assert set(mode) == {
            "hallucination",
            "numeric_fidelity",
            "answer_accuracy",
            "latency_p50_s",
            "latency_p95_s",
            "answered",
        }
    assert data["modes"]["llm_unverified"]["hallucination"] > 0
    assert data["modes"]["llm_verified"]["hallucination"] == 0
    assert 0 <= data["llm_kept_pct"] <= 100
    assert (root / "reports" / "ablation-tthc.md").is_file()


def test_no_report_writes_nothing(root: Path, factory) -> None:
    qa.run(_cfg(root, write_reports=False), engine_factory=factory)
    assert not (root / "reports").exists()


def test_skipped_without_eval_set(tmp_path: Path, factory) -> None:
    shutil.copytree(REPO / "config", tmp_path / "config")
    result = qa.run(_cfg(tmp_path), engine_factory=factory)
    assert not result.ran and "tập đánh giá" in result.reason


def test_skipped_when_kb_not_ready(root: Path) -> None:
    def broken(mode: str | None, kb: object | None) -> AnswerEngine:
        raise KnowledgeBaseNotReady()

    result = qa.run(_cfg(root), engine_factory=broken)
    assert not result.ran and "KB_NOT_READY" in result.reason


def test_invalid_row_is_rejected(root: Path, factory) -> None:
    path = root / "eval" / "sets" / "samples" / "qa_tthc.jsonl"
    bad = dict(ROWS[0], id="x-1", question="Số của tôi là 012345678901")
    path.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        qa.run(_cfg(root), engine_factory=factory)


def test_quick_takes_first_test_items_by_id() -> None:
    items = [dict(ROWS[i]) for i in (4, 0, 5, 2)]
    picked = qa.select_items(items, quick=True, quick_size=2)
    assert [i["id"] for i in picked] == ["t-1", "t-3"]
    assert [i["id"] for i in qa.select_items(items, quick=False, quick_size=2)] == [
        "t-1",
        "t-3",
        "t-5",
    ]


def test_kb_details_reads_normalize_report(tmp_path: Path, settings: RagSettings) -> None:
    records = tmp_path / "tthc" / "records"
    shutil.copytree(RECORDS, records)
    (tmp_path / "tthc" / "normalize_report.json").write_text(
        json.dumps(
            {
                "records_valid": 107,
                "pages_detail": 109,
                "flagged": 22,
                "coverage": {"phi_vnd": 10.3, "thanh_phan_ho_so": 81.3},
                "coverage_extra": {"phi_le_phi": 86.0},
            }
        ),
        encoding="utf-8",
    )
    kb_settings = dataclasses.replace(
        settings.kb, records_dir=records, index_dir=tmp_path / "tthc" / "index"
    )
    local = dataclasses.replace(settings, kb=kb_settings)
    got = qa.kb_details(local, procedures=3)
    assert got["records_valid"] == 107 and got["pages_detail"] == 109
    assert got["records_valid_pct"] == pytest.approx(98.17, abs=0.01)
    assert got["fee_coverage_pct"] == 10.3 and got["docs_coverage_pct"] == 81.3
    assert got["fee_text_coverage_pct"] == 86.0
    assert got["linh_vuc"] == 2 and got["chunks"] is None
    assert got["fetched_at_min"] <= got["fetched_at_max"]


def test_latest_json_carries_details(tmp_path: Path) -> None:
    result = SuiteResult(name="qa", metrics={"recall_at_5": 90.0}, details={"mode": "x"})
    path = write_latest_json(tmp_path, [result], [], quick=True)
    suite = json.loads(path.read_text(encoding="utf-8"))["suites"]["qa"]
    assert suite["details"] == {"mode": "x"}
    assert {"status", "reason", "samples", "metrics"} <= set(suite)


# ----------------------------------------------------------------------------- v2 (reviewer 25/9)
def test_unverified_outcome_is_graded_on_the_routed_procedure(settings: RagSettings) -> None:
    # The engine routed to 1.004222 while 1.004194 was retrieved first: the ablation must
    # judge the raw composer sentence against the procedure it was composed for.
    from types import SimpleNamespace

    from ctcv_agent.contracts import AskDiagnostics, AskResult, ProcedureCard

    records = [ProcedureRecord.load(p) for p in sorted(RECORDS.glob("*.json"))]
    kb = FakeKnowledgeBase(records, DENSE, settings=settings)
    routed = next(r for r in records if r.procedure_id == "1.004222")
    diag = AskDiagnostics(
        intent="phi_le_phi",
        retrieved_procedure_ids=["1.004194", "1.004222"],
        gate_passed=True,
        composer_sentence=GOOD_FEE,
        composer_doc_ids=[FEE_CHUNK],
    )
    with_card = AskResult(
        answer=f"{GOOD_FEE} Bác bấm nút xanh có chữ Nguồn để xem trang gốc nhé.",
        confidence=0.8,
        escalate=False,
        reason="ok",
        answer_mode="llm_verified",
        procedure=ProcedureCard.from_record(routed),
        diagnostics=diag,
    )
    assert qa._unverified(with_card, kb).procedure_id == "1.004222"
    no_card = SimpleNamespace(**{**with_card.__dict__, "procedure": None})
    assert qa._routed_procedure(no_card, kb) == "1.004222"
