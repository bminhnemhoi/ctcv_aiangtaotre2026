"""Step 3 — chunk_embed: chunk the clean TTHC records and embed them into the index (ADR-007).

Reads ``<clean>/tthc/records/*.json`` (written by ``normalize``) and writes
``<clean>/tthc/index/{chunks.jsonl, vectors.f32, index_meta.json}`` through
:func:`ctcv_agent.rag.build.build_index`. Embedding calls the local model server named in
``config/rag.yaml`` (Ollama, ``CTCV_OLLAMA_BASE_URL`` overrides), so the step only runs with
``--online``; without records or without ``--online`` it is skipped (exit 0) and writes
nothing. ``<clean>`` is ``cfg.clean()`` when the config provides it, else ``data/clean``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ctcv_agent.rag.build import (
    CHUNKS_FILE,
    META_FILE,
    VECTORS_FILE,
    build_index,
    format_report,
    make_embedder,
)
from ctcv_agent.rag.settings import load_rag_settings
from ctcv_core.errors import AppError
from ctcv_data.pipeline import PipelineConfig, StepReport

STEP = "chunk_embed"
NO_RECORDS = "chưa có bản ghi TTHC — chạy crawl --online rồi normalize trước"
NEEDS_ONLINE = "cần --online để gọi máy chủ embedding cục bộ (Ollama)"

__all__ = ["make_embedder", "run"]


def _clean_root(cfg: PipelineConfig) -> Path:
    """``cfg.clean()`` when available (data pipeline ≥ ADR-007), else ``<root>/data/clean``."""
    clean = getattr(cfg, "clean", None)
    return Path(clean()) if callable(clean) else Path(cfg.root) / "data" / "clean"


def _failed(exc: AppError, hosts: list[str]) -> StepReport:
    """Failure report carrying the error code, its reason and the hosts contacted."""
    details: dict[str, Any] = {"code": exc.code, **(exc.details or {}), "hosts_contacted": hosts}
    message = f"{exc.message_vi} ({exc.code})"
    if exc.code == "EMBEDDER_UNAVAILABLE":
        message += " — kiểm tra máy chủ Ollama và model embedding trong config/rag.yaml"
    return StepReport(STEP, "failed", message, details)


def run(cfg: PipelineConfig) -> StepReport:
    """Build the TTHC index (see module docstring)."""
    clean = _clean_root(cfg)
    records_dir = clean / "tthc" / "records"
    if not records_dir.is_dir() or not any(records_dir.glob("*.json")):
        return StepReport(STEP, "skipped", NO_RECORDS, {"records_dir": str(records_dir)})
    if not cfg.online:
        return StepReport(STEP, "skipped", NEEDS_ONLINE, {"records_dir": str(records_dir)})
    out_dir = clean / "tthc" / "index"
    embedder = None
    try:
        settings = load_rag_settings(Path(cfg.root))
        embedder = make_embedder(settings)
        report = build_index(records_dir, out_dir, embedder, settings)
    except AppError as exc:
        return _failed(exc, list(getattr(embedder, "hosts_contacted", [])))
    hosts = list(getattr(embedder, "hosts_contacted", []))
    details = {
        "records": report.records,
        "chunks": report.chunks,
        "dim": report.dim,
        "seconds": report.seconds,
        "vectors_sha256": report.vectors_sha256,
        "embed_model_id": embedder.model_id,
        "hosts_contacted": hosts,
    }
    outputs = [str(out_dir / name) for name in (CHUNKS_FILE, VECTORS_FILE, META_FILE)]
    return StepReport(STEP, "ok", format_report(report, hosts), details, outputs)
