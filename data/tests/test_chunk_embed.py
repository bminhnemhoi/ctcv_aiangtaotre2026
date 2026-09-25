"""Pipeline step chunk_embed: build the TTHC index from clean records (ADR-007 C1/C3)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

from ctcv_agent.rag.build import CHUNKS_FILE, META_FILE, VECTORS_FILE
from ctcv_agent.rag.embed import EmbedderUnavailable, HashEmbedder
from ctcv_core.config import clear_config_cache, find_repo_root
from ctcv_data.pipeline import PipelineConfig, chunk_embed, get_step

RECORD_FIXTURES = (
    find_repo_root() / "services" / "agent" / "tests" / "fixtures" / "tthc" / "records"
)


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throw-away repo root with the real config/ (rag, models, schemas, prompts)."""
    monkeypatch.delenv("CTCV_OLLAMA_BASE_URL", raising=False)
    target = tmp_path / "repo"
    shutil.copytree(find_repo_root() / "config", target / "config")
    (target / "data").mkdir()
    clear_config_cache()
    return target


def _with_records(clean: Path) -> Path:
    records = clean / "tthc" / "records"
    shutil.copytree(RECORD_FIXTURES, records)
    return records


class _NoEmbedder:
    """Fails the test if the step tries to embed anything."""

    def __call__(self, settings: object) -> None:
        raise AssertionError("không được gọi máy chủ embedding")


def test_step_is_registered() -> None:
    assert get_step("chunk_embed") is chunk_embed.run


def test_skips_without_records(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunk_embed, "make_embedder", _NoEmbedder())
    report = chunk_embed.run(PipelineConfig(root=root, online=True))
    assert report.status == "skipped" and report.exit_code == 0
    assert "chưa có bản ghi TTHC" in report.message


def test_skips_offline_even_with_records(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_records(root / "data" / "clean")
    monkeypatch.setattr(chunk_embed, "make_embedder", _NoEmbedder())
    report = chunk_embed.run(PipelineConfig(root=root, online=False))
    assert report.status == "skipped"
    assert "cần --online để gọi máy chủ embedding cục bộ (Ollama)" in report.message
    assert not (root / "data" / "clean" / "tthc" / "index").exists()


def test_builds_index_when_online(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_records(root / "data" / "clean")
    monkeypatch.setattr(chunk_embed, "make_embedder", lambda settings: HashEmbedder(dim=16))
    report = chunk_embed.run(PipelineConfig(root=root, online=True))
    assert report.status == "ok", report.message
    index = root / "data" / "clean" / "tthc" / "index"
    assert sorted(Path(p).name for p in report.outputs) == sorted(
        [CHUNKS_FILE, VECTORS_FILE, META_FILE]
    )
    assert all(Path(p).is_file() and Path(p).parent == index for p in report.outputs)
    details = report.details
    assert (details["records"], details["chunks"], details["dim"]) == (3, 24, 16)
    assert details["embed_model_id"] == "ctcv/hash-embedder-16"
    assert details["hosts_contacted"] == []
    meta = json.loads((index / META_FILE).read_text(encoding="utf-8"))
    assert meta["vectors_sha256"] == details["vectors_sha256"]
    assert "3 thủ tục" in report.message and "24 đoạn" in report.message


def test_uses_the_clean_dir_of_the_config(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clean = tmp_path / "elsewhere"
    _with_records(clean)
    monkeypatch.setattr(chunk_embed, "make_embedder", lambda settings: HashEmbedder(dim=8))
    cfg = SimpleNamespace(root=root, online=True, clean=lambda: clean)
    report = chunk_embed.run(cfg)  # type: ignore[arg-type]
    assert report.status == "ok", report.message
    assert (clean / "tthc" / "index" / META_FILE).is_file()


class _DownEmbedder:
    model_id = "BAAI/bge-m3"
    hosts_contacted = ["localhost:11434"]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbedderUnavailable("ConnectError")


def test_reports_failure_when_embedding_server_is_down(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_records(root / "data" / "clean")
    monkeypatch.setattr(chunk_embed, "make_embedder", lambda settings: _DownEmbedder())
    report = chunk_embed.run(PipelineConfig(root=root, online=True))
    assert report.status == "failed" and report.exit_code == 1
    assert report.details["code"] == "EMBEDDER_UNAVAILABLE"
    assert report.details["hosts_contacted"] == ["localhost:11434"]
    assert "Ollama" in report.message


def test_reports_failure_on_invalid_records(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    records = _with_records(root / "data" / "clean")
    (records / "2.000200.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(chunk_embed, "make_embedder", lambda settings: HashEmbedder(dim=8))
    report = chunk_embed.run(PipelineConfig(root=root, online=True))
    assert report.status == "failed"
    assert report.details["code"] == "KB_BUILD_FAILED"
    assert report.details["reason"] == "invalid_record"


def test_reports_failure_on_broken_config(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_records(root / "data" / "clean")
    (root / "config" / "rag.yaml").write_text("version: 2\n", encoding="utf-8")
    clear_config_cache()
    monkeypatch.setattr(chunk_embed, "make_embedder", _NoEmbedder())
    report = chunk_embed.run(PipelineConfig(root=root, online=True))
    assert report.status == "failed" and report.details["code"] == "CONFIG_ERROR"
