"""config/rag.yaml (ADR-007 C5): model names match the registry, endpoint is local, gate is sane."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from ctcv_agent.rag.types import SECTIONS
from ctcv_core.config import ConfigError, load_config

LOCAL_HOSTS = {"localhost", "127.0.0.1"}


def _alias_names(rag: dict, model_id: str) -> set[str]:
    return {
        name
        for alias in rag["serving_aliases"]
        if alias["model_id"] == model_id
        for name in alias["names"]
    }


@pytest.mark.parametrize("block", ["embed", "compose"])
def test_serving_name_matches_registry_model(block: str, load_yaml) -> None:
    rag = load_yaml("rag")
    models = load_yaml("models")["models"]
    model_id = models[rag[block]["model_ref"]]["id"]
    assert rag[block]["serving_name"] in _alias_names(rag, model_id), (block, model_id)


def test_every_alias_points_to_a_registered_model(load_yaml) -> None:
    ids = {m["id"] for m in load_yaml("models")["models"].values()}
    for alias in load_yaml("rag")["serving_aliases"]:
        assert alias["model_id"] in ids, alias["model_id"]


def test_serving_names_are_not_shared_between_models(load_yaml) -> None:
    names = [n for alias in load_yaml("rag")["serving_aliases"] for n in alias["names"]]
    assert len(names) == len(set(names))


def test_default_endpoint_is_local(load_yaml) -> None:
    serving = load_yaml("rag")["serving"]
    assert urlsplit(serving["endpoint"]).hostname in LOCAL_HOSTS
    assert serving["endpoint_env"] == "CTCV_OLLAMA_BASE_URL"


def test_compose_mode_override_template_only_is_accepted(tmp_env) -> None:
    tmp_env("CTCV_RAG_COMPOSE_MODE", "template_only")
    assert load_config("rag")["compose_mode"] == "template_only"


def test_compose_mode_override_llm_unverified_is_rejected(tmp_env) -> None:
    tmp_env("CTCV_RAG_COMPOSE_MODE", "llm_unverified")
    with pytest.raises(ConfigError, match="không khớp schema"):
        load_config("rag")


@pytest.mark.parametrize("key", ["CTCV_RAG_KB", "CTCV_RAG_GATE", "CTCV_RAG_SERVING"])
def test_non_scalar_blocks_cannot_be_overridden(key: str, tmp_env) -> None:
    tmp_env(key, "x")
    with pytest.raises(ConfigError):
        load_config("rag")


def test_default_compose_mode_is_verified(tmp_env) -> None:
    assert load_config("rag")["compose_mode"] == "llm_verified"


def test_intents_map_to_known_sections(load_yaml) -> None:
    rag = load_yaml("rag")
    assert set(rag["intents"]) <= set(rag["intent_sections"])
    assert "tong_quan" in rag["intent_sections"]
    assert "tong_quan" not in rag["intents"]  # fallback, never matched by keyword
    for intent, sections in rag["intent_sections"].items():
        assert set(sections) <= set(SECTIONS), intent


def test_intent_priority_order_starts_with_fees(load_yaml) -> None:
    # v2 (25/9, P8 h-008): han_phai_lam (the citizen's own deadline, "trong bao lâu phải đi
    # trình báo") must win over thoi_han ("bao lâu" = processing time), so it sits between.
    assert list(load_yaml("rag")["intents"])[:4] == [
        "phi_le_phi",
        "han_phai_lam",
        "thoi_han",
        "thanh_phan_ho_so",
    ]


def test_gate_thresholds_are_ordered(load_yaml) -> None:
    gate = load_yaml("rag")["gate"]
    assert gate["high_dense_score"] >= gate["min_dense_score"]
    for key in ("min_dense_score", "high_dense_score", "title_overlap_min", "lexical_min_support"):
        assert 0 < gate[key] < 1, key


def test_retrieval_sizes_are_consistent(load_yaml) -> None:
    retrieval = load_yaml("rag")["retrieval"]
    assert retrieval["context_chunks"] <= retrieval["top_k"]
    assert retrieval["context_chars_per_chunk"] <= retrieval["chunk_max_chars"]


def test_phrases_are_nfc_and_lower_case(load_yaml) -> None:
    rag = load_yaml("rag")
    phrases = [
        *(p for group in rag["retrieval"]["synonyms"] for p in group),
        *(p for pair in rag["retrieval"]["dialect_phrases"] for p in pair),
        *rag["gate"]["generic_words"],
        *(p for words in rag["intents"].values() for p in words),
    ]
    for phrase in phrases:
        assert phrase == unicodedata.normalize("NFC", phrase).casefold(), phrase


def test_dialect_phrases_never_rewrite_standard_words(load_yaml) -> None:
    sources = {src for src, _ in load_yaml("rag")["retrieval"]["dialect_phrases"]}
    assert "chi phí" not in sources
    assert "chi" not in sources  # single "chi" would break "chi phí"


def test_prompt_file_exists(load_yaml, config_dir: Path) -> None:
    prompt = load_yaml("rag")["compose"]["prompt"]
    assert (config_dir / "prompts" / f"{prompt}.md").is_file()


def test_kb_paths_are_relative_and_inside_data(load_yaml) -> None:
    kb = load_yaml("rag")["kb"]
    for key in ("records_dir", "index_dir"):
        assert not Path(kb[key]).is_absolute(), key
        assert kb[key].startswith("data/clean/"), key
    assert kb["skill"] in load_yaml("app")["skill_groups"]
