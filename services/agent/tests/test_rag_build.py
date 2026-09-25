"""build_index: records → chunks.jsonl + vectors.f32 + index_meta.json (ADR-007 C3)."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
from collections.abc import Sequence
from pathlib import Path

import pytest

from ctcv_agent.rag import build as build_mod
from ctcv_agent.rag.build import (
    CHUNKS_FILE,
    META_FILE,
    VECTORS_FILE,
    BuildReport,
    IndexBuildError,
    build_index,
    main,
    records_digest,
)
from ctcv_agent.rag.chunker import CHUNKER_VERSION, chunk_record
from ctcv_agent.rag.embed import EmbedderUnavailable, HashEmbedder
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_agent.rag.types import Chunk, ProcedureRecord, content_sha256_of
from ctcv_core.config import clear_config_cache

FIXTURE_RECORDS = Path(__file__).parent / "fixtures" / "tthc" / "records"
META_KEYS = {
    "version",
    "built_at",
    "chunker_version",
    "embed_model_ref",
    "embed_model_id",
    "embed_serving_name",
    "dim",
    "n_chunks",
    "records",
    "records_sha256",
    "vectors_sha256",
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> RagSettings:
    monkeypatch.delenv("CTCV_OLLAMA_BASE_URL", raising=False)
    clear_config_cache()
    return load_rag_settings()


@pytest.fixture
def records_dir(tmp_path: Path) -> Path:
    target = tmp_path / "records"
    shutil.copytree(FIXTURE_RECORDS, target)
    return target


def _records() -> list[ProcedureRecord]:
    records = [ProcedureRecord.load(p) for p in FIXTURE_RECORDS.glob("*.json")]
    return sorted(records, key=lambda r: r.procedure_id)


def _read_vectors(path: Path, dim: int) -> list[tuple[float, ...]]:
    data = path.read_bytes()
    count = len(data) // (4 * dim)
    return [struct.unpack_from(f"<{dim}f", data, i * 4 * dim) for i in range(count)]


def test_build_writes_aligned_files_and_meta(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    out = tmp_path / "index"
    embedder = HashEmbedder(dim=32)
    report = build_index(records_dir, out, embedder, settings)
    assert sorted(p.name for p in out.iterdir()) == sorted([CHUNKS_FILE, VECTORS_FILE, META_FILE])
    lines = (out / CHUNKS_FILE).read_text(encoding="utf-8").splitlines()
    meta = json.loads((out / META_FILE).read_text(encoding="utf-8"))
    assert set(meta) == META_KEYS
    assert meta["version"] == 1 and meta["chunker_version"] == CHUNKER_VERSION
    assert meta["embed_model_ref"] == settings.embed.model_ref == "embed"
    assert meta["embed_model_id"] == embedder.model_id
    assert meta["embed_serving_name"] is None
    assert meta["dim"] == 32 and meta["records"] == 3
    assert meta["n_chunks"] == len(lines) == report.chunks
    assert meta["built_at"].endswith("Z")
    vectors_bytes = (out / VECTORS_FILE).read_bytes()
    assert len(vectors_bytes) == len(lines) * 32 * 4
    assert meta["vectors_sha256"] == hashlib.sha256(vectors_bytes).hexdigest()
    assert meta["records_sha256"] == records_digest(_records())
    assert isinstance(report, BuildReport)
    assert (report.records, report.dim) == (3, 32)
    assert report.vectors_sha256 == meta["vectors_sha256"] and report.seconds >= 0.0


def test_chunk_lines_follow_chunker_order(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    out = tmp_path / "index"
    build_index(records_dir, out, HashEmbedder(dim=16), settings)
    written = [
        Chunk.model_validate_json(line)
        for line in (out / CHUNKS_FILE).read_text(encoding="utf-8").splitlines()
    ]
    size = settings.retrieval.chunk_max_chars
    expected = [c for r in _records() for c in chunk_record(r, size, skill=settings.kb.skill)]
    assert written == expected
    assert {c.skill for c in written} == {"dich-vu-cong"}


def test_row_i_is_the_normalised_vector_of_line_i(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    out = tmp_path / "index"
    embedder = HashEmbedder(dim=24)
    build_index(records_dir, out, embedder, settings)
    lines = (out / CHUNKS_FILE).read_text(encoding="utf-8").splitlines()
    rows = _read_vectors(out / VECTORS_FILE, 24)
    assert len(rows) == len(lines)
    for line, row in zip(lines, rows, strict=True):
        text = json.loads(line)["text"]
        assert math.fsum(v * v for v in row) == pytest.approx(1.0, abs=1e-5)
        assert list(row) == pytest.approx(embedder.embed([text])[0], abs=1e-6)


def test_build_is_deterministic(records_dir: Path, tmp_path: Path, settings: RagSettings) -> None:
    first = build_index(records_dir, tmp_path / "a", HashEmbedder(dim=16), settings)
    second = build_index(records_dir, tmp_path / "b", HashEmbedder(dim=16), settings)
    assert first.vectors_sha256 == second.vectors_sha256
    chunks_a = (tmp_path / "a" / CHUNKS_FILE).read_bytes()
    assert chunks_a == (tmp_path / "b" / CHUNKS_FILE).read_bytes()


def test_rebuild_replaces_previous_index_without_leftovers(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    out = tmp_path / "index"
    build_index(records_dir, out, HashEmbedder(dim=8), settings)
    build_index(records_dir, out, HashEmbedder(dim=16), settings)
    meta = json.loads((out / META_FILE).read_text(encoding="utf-8"))
    assert meta["dim"] == 16
    assert sorted(p.name for p in out.iterdir()) == sorted([CHUNKS_FILE, VECTORS_FILE, META_FILE])


class _FailingEmbedder:
    model_id = "test/failing"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbedderUnavailable("ConnectError")


def test_failed_build_keeps_the_previous_index(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    out = tmp_path / "index"
    build_index(records_dir, out, HashEmbedder(dim=8), settings)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(EmbedderUnavailable):
        build_index(records_dir, out, _FailingEmbedder(), settings)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


class _BadEmbedder:
    def __init__(self, vectors: list[list[float]] | None = None, *, drop: int = 0) -> None:
        self.model_id = "test/bad"
        self._vectors = vectors
        self._drop = drop

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self._vectors is not None:
            return [list(self._vectors[i % len(self._vectors)]) for i in range(len(texts))]
        return [[1.0, 0.0] for _ in texts[self._drop :]]


@pytest.mark.parametrize(
    ("embedder", "reason"),
    [
        (_BadEmbedder(drop=1), "vector_count"),
        (_BadEmbedder([[1.0, 0.0], [1.0]]), "vector_dim"),
        (_BadEmbedder([[0.0, 0.0]]), "bad_vector"),
        (_BadEmbedder([[]]), "vector_dim"),
    ],
)
def test_bad_vectors_are_rejected(
    records_dir: Path, tmp_path: Path, settings: RagSettings, embedder: _BadEmbedder, reason: str
) -> None:
    with pytest.raises(IndexBuildError) as exc:
        build_index(records_dir, tmp_path / "index", embedder, settings)
    assert exc.value.details["reason"] == reason
    assert not (tmp_path / "index" / META_FILE).exists()


def test_empty_records_dir_is_an_error(tmp_path: Path, settings: RagSettings) -> None:
    (tmp_path / "records").mkdir()
    with pytest.raises(IndexBuildError) as exc:
        build_index(tmp_path / "records", tmp_path / "index", HashEmbedder(), settings)
    assert exc.value.details["reason"] == "no_records"
    assert exc.value.code == "KB_BUILD_FAILED"
    with pytest.raises(IndexBuildError):
        build_index(tmp_path / "missing", tmp_path / "index", HashEmbedder(), settings)


def test_hand_edited_record_is_rejected(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    path = records_dir / "1.004222.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cach_thuc"][0]["phi_le_phi"] = "15.000 đồng"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(IndexBuildError) as exc:
        build_index(records_dir, tmp_path / "index", HashEmbedder(), settings)
    assert exc.value.details == {"reason": "content_hash_mismatch", "procedure_id": "1.004222"}


def test_records_without_any_content_are_an_error(tmp_path: Path, settings: RagSettings) -> None:
    raw = json.loads((FIXTURE_RECORDS / "2.000200.json").read_text(encoding="utf-8"))
    for key in ("linh_vuc", "co_quan_thuc_hien", "muc_do_dvc", "doi_tuong"):
        raw[key] = None
    for key in ("cach_thuc", "trinh_tu", "thanh_phan_ho_so", "can_cu_phap_ly", "bieu_mau"):
        raw[key] = []
    raw["yeu_cau_dieu_kien"] = raw["ket_qua"] = None
    raw["meta"]["sha256_content"] = content_sha256_of(raw)
    records = tmp_path / "records"
    records.mkdir()
    (records / "2.000200.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(IndexBuildError) as exc:
        build_index(records, tmp_path / "index", HashEmbedder(), settings)
    assert exc.value.details == {"reason": "no_chunks"}


@pytest.mark.parametrize("breakage", ["not json", '{"schema_version": 1}'])
def test_invalid_record_is_rejected(
    records_dir: Path, tmp_path: Path, settings: RagSettings, breakage: str
) -> None:
    (records_dir / "2.000200.json").write_text(breakage, encoding="utf-8")
    with pytest.raises(IndexBuildError) as exc:
        build_index(records_dir, tmp_path / "index", HashEmbedder(), settings)
    assert exc.value.details == {"reason": "invalid_record", "procedure_id": "2.000200"}


def test_file_name_must_match_procedure_id(
    records_dir: Path, tmp_path: Path, settings: RagSettings
) -> None:
    (records_dir / "2.000200.json").rename(records_dir / "khac.json")
    with pytest.raises(IndexBuildError) as exc:
        build_index(records_dir, tmp_path / "index", HashEmbedder(), settings)
    assert exc.value.details == {"reason": "file_name_mismatch", "procedure_id": "khac"}


def test_records_digest_depends_on_ids_and_content_hashes() -> None:
    records = _records()
    digest = records_digest(records)
    assert len(digest) == 64
    assert records_digest(list(reversed(records))) == digest
    assert records_digest(records[:2]) != digest


# ----------------------------------------------------------------------------- CLI
def test_cli_builds_with_configured_embedder(
    records_dir: Path,
    tmp_path: Path,
    settings: RagSettings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(build_mod, "make_embedder", lambda s: HashEmbedder(dim=8))
    out = tmp_path / "index"
    assert main(["--records-dir", str(records_dir), "--out-dir", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "3 thủ tục" in printed and "dim 8" in printed
    assert (out / META_FILE).is_file()


def test_cli_reports_unavailable_embedder(
    records_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(build_mod, "make_embedder", lambda s: _FailingEmbedder())
    code = main(["--records-dir", str(records_dir), "--out-dir", str(tmp_path / "index")])
    assert code == 1
    err = capsys.readouterr().err
    assert "[LỖI]" in err and "EMBEDDER_UNAVAILABLE" in err


def test_make_embedder_is_ollama_from_settings(settings: RagSettings) -> None:
    embedder = build_mod.make_embedder(settings)
    assert embedder.model_id == "BAAI/bge-m3"
    assert embedder.hosts_contacted == []
