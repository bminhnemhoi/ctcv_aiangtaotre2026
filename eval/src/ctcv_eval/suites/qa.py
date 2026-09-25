"""Suite ``qa`` — verified answers about administrative procedures (TTHC, ADR-007 C8).

Loads ``eval/sets/samples/qa_tthc.jsonl`` (generated) and ``qa_tthc_handwritten.jsonl``
(handwritten, optional), validates every line against ``qa_tthc.schema.json`` and runs the
``test`` split (``--quick``: the first ``quick_size`` test items by id) through the answer
engine. Metrics use the C8 names (:mod:`ctcv_eval.tthc_metrics`) plus
``answer_accuracy_text_only`` (answer text only, the procedure card ignored).

Ablation from the **same** run (one composer call per question):

* ``llm_verified`` — the engine's answer (composer sentence kept only when verified,
  otherwise the deterministic template);
* ``llm_unverified`` — the composer's raw sentence of that same call plus the closing line,
  scored against the chunks the composer said it used (all chunks of the procedure when it
  named none — the most lenient reading);
* ``template_only`` — a second engine sharing the knowledge base, mode ``template_only``
  (never calls the composer).

Unless ``--no-report``, ``eval/reports/ablation-tthc.{json,md}`` are written. The question
text is never logged or written to reports.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ctcv_agent.answer_templates import closing_for
from ctcv_agent.ask import AnswerEngine, build_engine
from ctcv_agent.contracts import ProcedureCard
from ctcv_agent.rag.settings import RagSettings
from ctcv_agent.rag.types import KnowledgeBase, KnowledgeBaseNotReady
from ctcv_agent.schemas import SessionContext
from ctcv_core.config import validate_against_schema
from ctcv_core.errors import AppError
from ctcv_eval.harness import HarnessConfig
from ctcv_eval.results import SuiteResult
from ctcv_eval.suites import SAMPLES_DIRNAME
from ctcv_eval.thresholds import load_thresholds
from ctcv_eval.tthc_metrics import (
    Outcome,
    answer_accuracy,
    compute_metrics,
    mode_summary,
    outcome_from_result,
    per_kind,
    undefined_metrics,
    unverified_outcome,
)

SUITE = "qa"
SET_FILES = ("qa_tthc.jsonl", "qa_tthc_handwritten.jsonl")
SCHEMA_FILE = "qa_tthc.schema.json"
REPORT_SPLIT = "test"
ABLATION_JSON = "ablation-tthc.json"
ABLATION_MD = "ablation-tthc.md"
MODE_ORDER = ("template_only", "llm_unverified", "llm_verified")
CTX = SessionContext(user_id="eval-qa", session_id="eval-qa-tthc")

EngineFactory = Callable[[str | None, KnowledgeBase | None], AnswerEngine]


def default_factory(mode: str | None, kb: KnowledgeBase | None) -> AnswerEngine:
    """Production wiring (file index, Ollama embedder and composer from ``config/rag.yaml``)."""
    return build_engine(mode=mode, kb=kb)


# ----------------------------------------------------------------------------- items
def load_items(root: Path) -> list[dict[str, Any]]:
    """Every line of the TTHC eval files, validated (``ConfigError`` on a bad line)."""
    samples = root.joinpath(*SAMPLES_DIRNAME)
    schema_path = samples / SCHEMA_FILE
    items: list[dict[str, Any]] = []
    for name in SET_FILES:
        path = samples / name
        if not path.is_file():
            continue
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        items.extend(json.loads(ln) for ln in lines)
    if items:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for item in items:
            validate_against_schema(item, schema, f"{SCHEMA_FILE}:{item.get('id')}")
    return items


def select_items(items: list[dict[str, Any]], *, quick: bool, quick_size: int) -> list[dict]:
    """Test split sorted by id; ``quick`` keeps the first ``quick_size``."""
    test = sorted((i for i in items if i["split"] == REPORT_SPLIT), key=lambda i: i["id"])
    return test[:quick_size] if quick and quick_size > 0 else test


# ----------------------------------------------------------------------------- knowledge base
def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _record_facts(records_dir: Path) -> tuple[int, str | None, str | None]:
    """Number of distinct ``linh_vuc`` and min/max ``meta.fetched_at`` of the records."""
    fields: set[str] = set()
    fetched: list[str] = []
    for path in sorted(records_dir.glob("*.json")):
        data = _read_json(path)
        if data.get("linh_vuc"):
            fields.add(data["linh_vuc"])
        if data.get("meta", {}).get("fetched_at"):
            fetched.append(data["meta"]["fetched_at"])
    return len(fields), min(fetched, default=None), max(fetched, default=None)


def kb_details(settings: RagSettings, *, procedures: int) -> dict[str, Any]:
    """C8 ``details.kb`` from the records, ``index_meta.json`` and ``normalize_report.json``."""
    records_dir = settings.kb.records_dir
    report = _read_json(records_dir.parent / "normalize_report.json")
    meta = _read_json(settings.kb.index_dir / "index_meta.json")
    linh_vuc, first, last = _record_facts(records_dir)
    valid, pages = report.get("records_valid"), report.get("pages_detail")
    coverage, extra = report.get("coverage", {}), report.get("coverage_extra", {})
    return {
        "procedures": procedures,
        "chunks": meta.get("n_chunks"),
        "linh_vuc": linh_vuc,
        "fetched_at_min": first,
        "fetched_at_max": last,
        "records_valid": valid,
        "pages_detail": pages,
        "records_valid_pct": round(100.0 * valid / pages, 2) if valid and pages else None,
        "fee_coverage_pct": coverage.get("phi_vnd"),
        "fee_text_coverage_pct": extra.get("phi_le_phi"),
        "docs_coverage_pct": coverage.get("thanh_phan_ho_so"),
        "flagged_records": report.get("flagged"),
    }


# ----------------------------------------------------------------------------- running
def _chunk_text(kb: KnowledgeBase) -> Callable[[str], str | None]:
    def _text(doc_id: str) -> str | None:
        chunk = kb.get_chunk(doc_id)
        return chunk.text if chunk is not None else None

    return _text


def _routed_procedure(result: Any, kb: KnowledgeBase) -> str | None:
    """Procedure the engine actually routed to (the composer's context), not the first hit.

    The engine may prefer a same-name procedure at commune level or a better-named hit over
    the first retrieved one (reviewer 25/9: scoring ``retrieved[0]`` graded the ablation
    against the wrong procedure). Order: the card, the composer's cited chunks, the first hit.
    """
    if result.procedure is not None:
        return str(result.procedure.procedure_id)
    diag = result.diagnostics
    for doc_id in diag.composer_doc_ids:
        chunk = kb.get_chunk(doc_id)
        if chunk is not None:
            return chunk.procedure_id
    return diag.retrieved_procedure_ids[0] if diag.retrieved_procedure_ids else None


def _unverified(result: Any, kb: KnowledgeBase) -> Outcome:
    """The raw-composer outcome of the same call (see module docstring)."""
    diag = result.diagnostics
    pid = _routed_procedure(result, kb)
    record = kb.get_procedure(pid) if pid else None
    card = ProcedureCard.from_record(record) if record is not None else None
    texts = [t for t in map(_chunk_text(kb), diag.composer_doc_ids) if t]
    if not texts and pid:
        texts = [c.text for c in kb.chunks_for(pid)]
    timings = diag.timings_ms
    latency = (timings.get("retrieve", 0.0) + timings.get("compose", 0.0)) / 1000.0
    return unverified_outcome(result, closing_for(diag.intent or ""), card, texts, latency)


def _timed(engine: AnswerEngine, question: str) -> tuple[Any, float]:
    started = time.perf_counter()
    result = engine.ask(question, CTX)
    return result, time.perf_counter() - started


def run_items(
    items: list[dict[str, Any]], main: AnswerEngine, template: AnswerEngine
) -> dict[str, Any]:
    """Ask every item once per engine; return outcomes per mode and run statistics."""
    kb = main.kb
    modes: dict[str, list[tuple[dict, Outcome]]] = {m: [] for m in MODE_ORDER}
    stats = {"hosts": set(), "composer_failures": 0, "composer_sentences": 0, "kept": 0}
    stats["degraded"] = 0
    for item in items:
        result, seconds = _timed(main, item["question"])
        diag = result.diagnostics
        stats["hosts"].update(diag.hosts_contacted)
        stats["composer_failures"] += diag.composer_error is not None
        stats["degraded"] += diag.degraded
        if diag.composer_sentence and diag.gate_passed:
            stats["composer_sentences"] += 1
            stats["kept"] += result.answer_mode == "llm_verified"
        modes["llm_verified"].append((item, outcome_from_result(result, seconds, _chunk_text(kb))))
        modes["llm_unverified"].append((item, _unverified(result, kb)))
        t_result, t_seconds = _timed(template, item["question"])
        stats["hosts"].update(t_result.diagnostics.hosts_contacted)
        modes["template_only"].append(
            (item, outcome_from_result(t_result, t_seconds, _chunk_text(kb)))
        )
    return {"modes": modes, **stats}


def _kept_pct(run: dict[str, Any]) -> float | None:
    total = run["composer_sentences"]
    return round(100.0 * run["kept"] / total, 2) if total else None


def _details(
    items: list[dict], evaluated: list[dict], run: dict[str, Any], main: AnswerEngine, metrics
) -> dict[str, Any]:
    splits = {s: sum(i["split"] == s for i in items) for s in ("dev", "test")}
    return {
        "kb": kb_details(main.settings, procedures=main.kb.procedure_count()),
        "split_sizes": splits,
        "evaluated": len(evaluated),
        "per_kind": per_kind(run["modes"]["llm_verified"]),
        "network_hosts": sorted(run["hosts"]),
        "composer_failures": run["composer_failures"],
        "composer_sentences": run["composer_sentences"],
        "llm_kept_pct": _kept_pct(run),
        "degraded_answers": run["degraded"],
        "mode": main.mode,
        "undefined_metrics": undefined_metrics(metrics),
        "sources": sorted({i["source"] for i in evaluated}),
    }


def run(cfg: HarnessConfig, *, engine_factory: EngineFactory | None = None) -> SuiteResult:
    """Run the TTHC suite on the test split (see module docstring)."""
    items = load_items(cfg.root)
    if not items:
        return SuiteResult.skipped(SUITE, "chưa có tập đánh giá TTHC (eval/sets/samples)")
    quick_size = load_thresholds(cfg.root)[SUITE].quick_size
    evaluated = select_items(items, quick=cfg.quick, quick_size=quick_size)
    factory = engine_factory or default_factory
    try:
        main = factory(None, None)
        template = factory("template_only", main.kb)
        run_out = run_items(evaluated, main, template)
    except KnowledgeBaseNotReady as exc:
        return SuiteResult.skipped(SUITE, f"kho thủ tục chưa sẵn sàng ({exc.code})")
    except AppError as exc:
        return SuiteResult.skipped(SUITE, f"không chạy được bộ máy trả lời ({exc.code})")
    lexical = main.settings.gate.lexical_min_support
    verified = run_out["modes"]["llm_verified"]
    metrics = compute_metrics(verified, lexical)
    text_only = answer_accuracy(verified, text_only=True)
    if text_only is not None:
        metrics["answer_accuracy_text_only"] = text_only
    details = _details(items, evaluated, run_out, main, metrics)
    if cfg.write_reports:
        write_ablation(cfg.reports(), run_out, lexical, len(evaluated))
    return SuiteResult(name=SUITE, metrics=metrics, samples=len(evaluated), details=details)


# ----------------------------------------------------------------------------- ablation report
def ablation_payload(run_out: dict[str, Any], lexical: float, n: int) -> dict[str, Any]:
    """C8 ``ablation-tthc.json`` content."""
    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "split": REPORT_SPLIT,
        "n_in_scope": n,
        "llm_kept_pct": _kept_pct(run_out),
        "composer_sentences": run_out["composer_sentences"],
        "modes": {m: mode_summary(run_out["modes"][m], lexical) for m in MODE_ORDER},
    }


def _cell(value: Any) -> str:
    return "chưa đo" if value is None else f"{value:g}"


def render_ablation_md(payload: dict[str, Any]) -> str:
    """Vietnamese Markdown twin of the ablation JSON."""
    head = (
        "| Chế độ | Ảo giác (%) | Số đúng nguồn (%) | Trả lời đúng (%) "
        "| p50 (s) | p95 (s) | Đã trả lời |"
    )
    lines = [
        f"# Ablation hỏi đáp thủ tục — {payload['generated_at'][:10]}\n",
        f"Tập `{payload['split']}`, {payload['n_in_scope']} câu; ba chế độ lấy từ cùng một lượt "
        "gọi mô hình (xem `eval/README.md`). Sinh tự động, không sửa tay.\n",
        head,
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for mode, row in payload["modes"].items():
        cells = [row[k] for k in ("hallucination", "numeric_fidelity", "answer_accuracy")]
        cells += [row["latency_p50_s"], row["latency_p95_s"], row["answered"]]
        lines.append(f"| {mode} | " + " | ".join(_cell(c) for c in cells) + " |")
    lines.append(
        f"\nCâu do mô hình viết được giữ sau kiểm chứng: {_cell(payload['llm_kept_pct'])} % "
        f"(trên {payload['composer_sentences']} câu mô hình đề xuất khi đã qua cổng)."
    )
    return "\n".join(lines) + "\n"


def write_ablation(directory: Path, run_out: dict[str, Any], lexical: float, n: int) -> Path:
    """Write ``ablation-tthc.json`` and ``ablation-tthc.md``; return the JSON path."""
    payload = ablation_payload(run_out, lexical, n)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ABLATION_JSON
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / ABLATION_MD).write_text(render_ablation_md(payload), encoding="utf-8")
    return path
