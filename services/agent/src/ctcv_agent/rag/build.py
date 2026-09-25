"""Build the TTHC retrieval index from normalised records (ADR-007 C3).

``build_index`` reads ``<records_dir>/<procedure_id>.json`` (validated as
:class:`~ctcv_agent.rag.types.ProcedureRecord`, content hash re-checked), splits every record
with :func:`~ctcv_agent.rag.chunker.chunk_record`, embeds the chunk texts and writes three
files into ``out_dir``:

* ``chunks.jsonl`` — one :class:`~ctcv_agent.rag.types.Chunk` per line;
* ``vectors.f32`` — row *i* = L2-normalised float32 little-endian vector of line *i*;
* ``index_meta.json`` — version, build time, chunker version, embedding model, dimension,
  counts and the SHA-256 of the records set and of ``vectors.f32``.

Files are staged next to their target and swapped in with :func:`os.replace`; the old
``index_meta.json`` is removed first and the new one written last, so a reader sees either
the previous complete index, "not ready", or the new complete index — never a mix.

CLI: ``uv run python -m ctcv_agent.rag.build [--records-dir DIR] [--out-dir DIR]``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from array import array
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ctcv_agent.rag.chunker import CHUNKER_VERSION, chunk_record
from ctcv_agent.rag.embed import Embedder, OllamaEmbedder, l2_normalize
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import Chunk, ProcedureRecord, content_sha256_of
from ctcv_core.errors import AppError

INDEX_VERSION = 1
CHUNKS_FILE = "chunks.jsonl"
VECTORS_FILE = "vectors.f32"
META_FILE = "index_meta.json"
_LOG = logging.getLogger(__name__)


class IndexBuildError(AppError):
    """The index cannot be built from these records (reason + procedure id in ``details``)."""

    CODE = "KB_BUILD_FAILED"
    STATUS = 500

    def __init__(self, message_vi: str, reason: str, procedure_id: str | None = None) -> None:
        """Create the error; ``details`` carries the machine reason and the procedure id."""
        details: dict[str, Any] = {"reason": reason}
        if procedure_id is not None:
            details["procedure_id"] = procedure_id
        super().__init__(self.CODE, message_vi, self.STATUS, details)


@dataclass(frozen=True)
class BuildReport:
    """Summary of one build."""

    records: int
    chunks: int
    dim: int
    seconds: float
    vectors_sha256: str


# ----------------------------------------------------------------------------- shared helpers
def records_digest(records: Iterable[ProcedureRecord]) -> str:
    """SHA-256 over sorted ``<procedure_id>:<sha256_content>`` lines (order independent)."""
    lines = sorted(f"{r.procedure_id}:{r.meta.sha256_content}\n" for r in records)
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def vectors_to_bytes(vectors: Sequence[Sequence[float]]) -> bytes:
    """Pack rows as float32 little-endian, row after row."""
    packed = array("f")
    for row in vectors:
        packed.extend(row)
    if sys.byteorder == "big":  # pragma: no cover - every supported host is little-endian
        packed.byteswap()
    return packed.tobytes()


def vectors_from_bytes(data: bytes) -> array:
    """Unpack float32 little-endian bytes into a flat native ``array('f')``."""
    flat = array("f")
    flat.frombytes(data)
    if sys.byteorder == "big":  # pragma: no cover - every supported host is little-endian
        flat.byteswap()
    return flat


def utc_now_z() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- records
def _load_record(path: Path) -> ProcedureRecord:
    """Validate one record file and re-check its content hash and file name."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        record = ProcedureRecord.model_validate(raw)
    except (ValueError, ValidationError) as exc:
        raise IndexBuildError(
            f"Bản ghi {path.name} không hợp lệ theo lược đồ TTHC v1.", "invalid_record", path.stem
        ) from exc
    if record.procedure_id != path.stem:
        raise IndexBuildError(
            f"Tên file {path.name} phải là <procedure_id>.json.", "file_name_mismatch", path.stem
        )
    if content_sha256_of(raw) != record.meta.sha256_content:
        raise IndexBuildError(
            f"Bản ghi {path.name} đã bị sửa sau khi chuẩn hóa (sha256_content không khớp).",
            "content_hash_mismatch",
            record.procedure_id,
        )
    return record


def load_records(records_dir: Path) -> list[ProcedureRecord]:
    """Load every ``*.json`` record of ``records_dir`` sorted by ``procedure_id``."""
    paths = sorted(Path(records_dir).glob("*.json")) if Path(records_dir).is_dir() else []
    if not paths:
        raise IndexBuildError(f"Chưa có bản ghi TTHC trong {records_dir}.", "no_records")
    return sorted((_load_record(p) for p in paths), key=lambda r: r.procedure_id)


# ----------------------------------------------------------------------------- vectors
def _embed_chunks(chunks: Sequence[Chunk], embedder: Embedder) -> list[list[float]]:
    """Embed chunk texts and check count, dimension and norm of every vector."""
    if not chunks:
        raise IndexBuildError("Các bản ghi không có đoạn nội dung nào để lập chỉ mục.", "no_chunks")
    vectors = embedder.embed([chunk.text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise IndexBuildError("Số vector trả về khác số đoạn văn.", "vector_count")
    dims = {len(v) for v in vectors}
    if len(dims) != 1 or min(dims) < 1:
        raise IndexBuildError("Các vector không cùng số chiều.", "vector_dim")
    try:
        return [l2_normalize(v) for v in vectors]
    except ValueError as exc:
        raise IndexBuildError("Có vector bằng 0 hoặc không hữu hạn.", "bad_vector") from exc


# ----------------------------------------------------------------------------- writing
def _stage(target: Path, data: bytes) -> Path:
    """Write ``data`` to a hidden temporary sibling of ``target`` and return its path."""
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_bytes(data)
    return tmp


def _swap_in(out_dir: Path, payloads: dict[str, bytes]) -> None:
    """Atomically replace the index files; metadata goes last (see module docstring)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    try:
        for name, data in payloads.items():
            staged[name] = _stage(out_dir / name, data)
        (out_dir / META_FILE).unlink(missing_ok=True)
        for name in (CHUNKS_FILE, VECTORS_FILE, META_FILE):
            os.replace(staged.pop(name), out_dir / name)
    finally:
        for leftover in staged.values():
            leftover.unlink(missing_ok=True)


def _chunks_bytes(chunks: Sequence[Chunk]) -> bytes:
    lines = (json.dumps(c.model_dump(mode="json"), ensure_ascii=False) + "\n" for c in chunks)
    return "".join(lines).encode("utf-8")


def _meta(
    records: Sequence[ProcedureRecord],
    n_chunks: int,
    dim: int,
    vectors_sha256: str,
    embedder: Embedder,
    settings: RagSettings,
) -> dict[str, Any]:
    return {
        "version": INDEX_VERSION,
        "built_at": utc_now_z(),
        "chunker_version": CHUNKER_VERSION,
        "embed_model_ref": settings.embed.model_ref,
        "embed_model_id": embedder.model_id,
        "embed_serving_name": getattr(embedder, "serving_name", None),
        "dim": dim,
        "n_chunks": n_chunks,
        "records": len(records),
        "records_sha256": records_digest(records),
        "vectors_sha256": vectors_sha256,
    }


def build_index(
    records_dir: Path, out_dir: Path, embedder: Embedder, settings: RagSettings
) -> BuildReport:
    """Build ``chunks.jsonl``, ``vectors.f32`` and ``index_meta.json`` (see module docstring).

    Raises:
        IndexBuildError: no records, invalid/edited record, or unusable vectors.
        EmbedderUnavailable: the embedder failed (the previous index is left untouched).
    """
    started = time.perf_counter()
    records = load_records(Path(records_dir))
    size, skill = settings.retrieval.chunk_max_chars, settings.kb.skill
    chunks = [c for r in records for c in chunk_record(r, size, skill=skill)]
    vectors = _embed_chunks(chunks, embedder)
    blob = vectors_to_bytes(vectors)
    digest = hashlib.sha256(blob).hexdigest()
    meta = _meta(records, len(chunks), len(vectors[0]), digest, embedder, settings)
    meta_bytes = (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _swap_in(
        Path(out_dir),
        {CHUNKS_FILE: _chunks_bytes(chunks), VECTORS_FILE: blob, META_FILE: meta_bytes},
    )
    seconds = round(time.perf_counter() - started, 3)
    _LOG.info(
        "tthc index built: %d records, %d chunks, dim %d", len(records), len(chunks), meta["dim"]
    )
    return BuildReport(len(records), len(chunks), meta["dim"], seconds, digest)


# ----------------------------------------------------------------------------- CLI
def make_embedder(settings: RagSettings) -> Embedder:
    """Embedder used by the CLI and the data pipeline: the configured Ollama server."""
    return OllamaEmbedder(settings)


def format_report(report: BuildReport, hosts: Sequence[str] = ()) -> str:
    """One Vietnamese line describing a finished build."""
    line = (
        f"{report.records} thủ tục, {report.chunks} đoạn, dim {report.dim}, "
        f"{report.seconds:.1f} s, vectors sha256 {report.vectors_sha256[:12]}…"
    )
    return f"{line} (máy chủ: {', '.join(hosts)})" if hosts else line


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; exit 0 on success, 1 on a build or embedder error."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m ctcv_agent.rag.build", description=__doc__)
    parser.add_argument("--records-dir", type=Path, default=None, help="mặc định: kb.records_dir")
    parser.add_argument("--out-dir", type=Path, default=None, help="mặc định: kb.index_dir")
    args = parser.parse_args(argv)
    settings = load_rag_settings()
    embedder = make_embedder(settings)
    records_dir = args.records_dir or settings.records_dir
    out_dir = args.out_dir or settings.index_dir
    try:
        report = build_index(records_dir, out_dir, embedder, settings)
    except AppError as exc:
        print(f"[LỖI] {exc.code}: {exc.message_vi} {exc.details or ''}".rstrip(), file=sys.stderr)
        return 1
    print(f"[OK] {format_report(report, getattr(embedder, 'hosts_contacted', ()))} → {out_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())
