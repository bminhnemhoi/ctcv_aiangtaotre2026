"""ADR-007 C4/C5: RagSettings resolves config/rag.yaml + models.yaml into absolute, typed values."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import pytest
import yaml

from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_core.config import ConfigError, clear_config_cache, find_repo_root

ENDPOINT_ENV = "CTCV_OLLAMA_BASE_URL"


@pytest.fixture
def no_endpoint_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENDPOINT_ENV, raising=False)
    monkeypatch.delenv("CTCV_RAG_COMPOSE_MODE", raising=False)
    clear_config_cache()


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """A throw-away repo root with copies of the rag/models configs and their schemas."""
    repo = find_repo_root()
    (tmp_path / "config" / "schemas").mkdir(parents=True)
    (tmp_path / "config" / "prompts").mkdir()
    for name in ("rag", "models"):
        shutil.copy(repo / "config" / f"{name}.yaml", tmp_path / "config" / f"{name}.yaml")
        shutil.copy(
            repo / "config" / "schemas" / f"{name}.schema.json",
            tmp_path / "config" / "schemas" / f"{name}.schema.json",
        )
    (tmp_path / "config" / "prompts" / "tthc_ask.v1.md").write_text("x", encoding="utf-8")
    clear_config_cache()
    return tmp_path


def _edit_rag(root: Path, block: str, key: str, value: object) -> None:
    path = root / "config" / "rag.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data[block][key] = value
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    clear_config_cache()


def test_settings_is_a_frozen_dataclass(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    assert isinstance(settings, RagSettings)
    assert dataclasses.is_dataclass(settings)
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.compose_mode = "template_only"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.gate.min_dense_score = 0.0  # type: ignore[misc]


def test_paths_are_absolute_under_repo_root(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    root = find_repo_root()
    assert settings.root == root
    assert settings.records_dir == root / "data" / "clean" / "tthc" / "records"
    assert settings.index_dir == root / "data" / "clean" / "tthc" / "index"
    assert settings.kb.records_dir.is_absolute()
    assert settings.compose.prompt_path == root / "config" / "prompts" / "tthc_ask.v1.md"
    assert settings.compose.prompt_path.is_file()


def test_default_endpoint_is_config_value(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    assert settings.endpoint == "http://localhost:11434"
    assert settings.serving.endpoint_env == ENDPOINT_ENV
    assert settings.serving.timeout_s == 120


def test_endpoint_comes_from_env_when_set(
    no_endpoint_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENDPOINT_ENV, "http://127.0.0.1:11500/")
    assert load_rag_settings().endpoint == "http://127.0.0.1:11500"


def test_blank_env_endpoint_falls_back_to_config(
    no_endpoint_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENDPOINT_ENV, "   ")
    assert load_rag_settings().endpoint == "http://localhost:11434"


@pytest.mark.parametrize("value", ["ftp://host:21", "localhost:11434", "http://"])
def test_invalid_env_endpoint_is_rejected(
    no_endpoint_env: None, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(ENDPOINT_ENV, value)
    with pytest.raises(ConfigError, match=ENDPOINT_ENV):
        load_rag_settings()


def test_model_ids_resolved_from_models_yaml(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    assert settings.embed.model_ref == "embed"
    assert settings.embed_model_id == "BAAI/bge-m3"
    assert settings.embed_serving_name == "bge-m3"
    assert settings.embed.batch_size == 16
    assert settings.compose_model_id == "Qwen/Qwen3.5-2B"
    assert settings.compose_serving_name == "qwen3.5:2b"
    assert settings.compose.api == "ollama_chat"
    assert settings.compose.think is False
    assert settings.compose.temperature == 0.0
    assert settings.compose.max_output_tokens == 160
    assert settings.compose.keep_alive == "30m"


def test_retrieval_gate_and_demo_values(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    assert settings.retrieval.top_k == 5
    assert settings.retrieval.chunk_max_chars == 1200
    assert settings.retrieval.accent_fold is True
    assert ("cần chi", "cần gì") in settings.retrieval.dialect_phrases
    assert settings.retrieval.synonyms[0][0] == "căn cước"
    assert settings.gate.min_dense_score == 0.45
    assert settings.gate.high_dense_score == 0.70
    assert "thủ tục" in settings.gate.generic_words
    assert settings.demo_staff_username == "canbo-demo"
    assert settings.kb.skill == "dich-vu-cong"
    assert settings.kb.source_portal == "Cổng Dịch vụ công - Bộ Công an"


def test_intents_keep_priority_order(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    assert list(settings.intents)[0] == "phi_le_phi"
    assert list(settings.intents)[-1] == "trinh_tu"
    assert settings.intents["phi_le_phi"][0] == "lệ phí"
    assert settings.intent_sections["tong_quan"] == ("tong_quan", "trinh_tu")
    with pytest.raises(TypeError):
        settings.intent_sections["x"] = ("y",)  # type: ignore[index]


def test_settings_are_hashable_for_caching(no_endpoint_env: None) -> None:
    settings = load_rag_settings()
    assert hash(settings) == hash(settings)
    assert {settings: 1}[settings] == 1


def test_compose_mode_env_override(no_endpoint_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTCV_RAG_COMPOSE_MODE", "template_only")
    clear_config_cache()
    assert load_rag_settings().compose_mode == "template_only"


def test_custom_root_resolves_paths_against_it(no_endpoint_env: None, tmp_root: Path) -> None:
    settings = load_rag_settings(tmp_root)
    assert settings.root == tmp_root.resolve()
    assert settings.records_dir == tmp_root.resolve() / "data" / "clean" / "tthc" / "records"


def test_unknown_model_ref_is_rejected(no_endpoint_env: None, tmp_root: Path) -> None:
    _edit_rag(tmp_root, "embed", "model_ref", "no_such_model")
    with pytest.raises(ConfigError, match="no_such_model"):
        load_rag_settings(tmp_root)


def test_serving_name_must_match_registry_model(no_endpoint_env: None, tmp_root: Path) -> None:
    _edit_rag(tmp_root, "compose", "serving_name", "qwen3.5:9b")
    with pytest.raises(ConfigError, match="qwen3.5:9b"):
        load_rag_settings(tmp_root)


def test_missing_prompt_file_is_rejected(no_endpoint_env: None, tmp_root: Path) -> None:
    (tmp_root / "config" / "prompts" / "tthc_ask.v1.md").unlink()
    with pytest.raises(ConfigError, match="tthc_ask.v1"):
        load_rag_settings(tmp_root)


# ----------------------------------------------------------------------------- Ollama options
NUM_GPU_ENV = "CTCV_OLLAMA_NUM_GPU"


def test_no_ollama_options_by_default(no_endpoint_env: None, monkeypatch) -> None:
    monkeypatch.delenv(NUM_GPU_ENV, raising=False)
    s = load_rag_settings()
    assert s.serving.num_gpu_env == NUM_GPU_ENV
    assert dict(s.serving.ollama_options) == {}


@pytest.mark.parametrize(("raw", "value"), [("0", 0), (" 99 ", 99)])
def test_num_gpu_comes_from_env_for_a_cpu_only_run(
    no_endpoint_env: None, monkeypatch, raw: str, value: int
) -> None:
    monkeypatch.setenv(NUM_GPU_ENV, raw)
    assert dict(load_rag_settings().serving.ollama_options) == {"num_gpu": value}


@pytest.mark.parametrize("raw", ["-1", "abc", "1.5"])
def test_invalid_num_gpu_env_is_rejected(no_endpoint_env: None, monkeypatch, raw: str) -> None:
    monkeypatch.setenv(NUM_GPU_ENV, raw)
    with pytest.raises(ConfigError):
        load_rag_settings()


def test_file_ollama_options_are_kept_and_env_overrides_num_gpu(
    no_endpoint_env: None, tmp_root: Path, monkeypatch
) -> None:
    monkeypatch.delenv(NUM_GPU_ENV, raising=False)
    _edit_rag(tmp_root, "serving", "ollama_options", {"num_gpu": 5})
    assert dict(load_rag_settings(tmp_root).serving.ollama_options) == {"num_gpu": 5}
    monkeypatch.setenv(NUM_GPU_ENV, "0")
    assert dict(load_rag_settings(tmp_root).serving.ollama_options) == {"num_gpu": 0}


def test_unknown_ollama_option_is_rejected_by_the_schema(
    no_endpoint_env: None, tmp_root: Path
) -> None:
    _edit_rag(tmp_root, "serving", "ollama_options", {"num_ctx": 4096})
    with pytest.raises(ConfigError):
        load_rag_settings(tmp_root)
