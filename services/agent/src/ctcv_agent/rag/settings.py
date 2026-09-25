"""Typed, resolved view of ``config/rag.yaml`` (ADR-007 C5) joined with ``config/models.yaml``.

``load_rag_settings()`` validates both files through :func:`ctcv_core.config.load_config`
(JSON Schema + the only allowed override ``CTCV_RAG_COMPOSE_MODE``), turns relative data
paths into absolute ones under the repository root, resolves ``model_ref`` into the model
id of the registry and checks that every serving name is a declared alias of that id, so a
model can never be swapped by editing ``rag.yaml`` alone. The serving endpoint comes from the
environment variable named by ``serving.endpoint_env`` when it is set, else from the file.

``serving.ollama_options`` (optional) are extra Ollama ``options`` sent with every embed and
chat request; the variable named by ``serving.num_gpu_env`` (``CTCV_OLLAMA_NUM_GPU``), when
set to an integer ≥ 0, overrides ``num_gpu`` — ``0`` keeps the models on the CPU so a
CPU-only latency can be measured honestly on a machine that has a GPU. Unset by default.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from ctcv_core.config import ConfigError, find_repo_root, load_config

PROMPTS_SUBDIR = ("config", "prompts")


@dataclass(frozen=True)
class KbSettings:
    """Where records and the index live, and how chunks are labelled."""

    records_dir: Path
    index_dir: Path
    skill: str
    source_portal: str


@dataclass(frozen=True)
class ServingSettings:
    """Local model server (Ollama) endpoint, request timeout and extra Ollama options."""

    endpoint: str
    endpoint_env: str
    timeout_s: float
    num_gpu_env: str | None = None
    ollama_options: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class EmbedSettings:
    """Embedding model: registry key, resolved id, served name and batch size."""

    model_ref: str
    model_id: str
    serving_name: str
    batch_size: int


@dataclass(frozen=True)
class ComposeSettings:
    """Sentence composer model and decoding parameters."""

    model_ref: str
    model_id: str
    serving_name: str
    api: str
    max_output_tokens: int
    temperature: float
    think: bool
    keep_alive: str
    prompt: str
    prompt_path: Path


@dataclass(frozen=True)
class RetrievalSettings:
    """Hybrid retrieval parameters and query rewriting lists."""

    top_k: int
    context_chunks: int
    context_chars_per_chunk: int
    chunk_max_chars: int
    rrf_k: int
    bm25_k1: float
    bm25_b: float
    accent_fold: bool
    synonyms: tuple[tuple[str, ...], ...]
    dialect_phrases: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GateSettings:
    """Thresholds deciding whether retrieved sources are good enough to answer."""

    min_dense_score: float
    high_dense_score: float
    title_overlap_min: float
    lexical_min_support: float
    confidence_weight_dense: float
    generic_words: tuple[str, ...]
    out_of_scope_phrases: tuple[str, ...] = ()
    document_markers: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class RagSettings:
    """All C5 keys, resolved. Compared and hashed by identity (safe as a cache key).

    ``intents`` iterates in priority order; ``intent_sections`` maps every intent (plus the
    ``tong_quan`` fallback) to the sections it reads. Both mappings are read-only.
    """

    root: Path
    compose_mode: str
    kb: KbSettings
    serving: ServingSettings
    embed: EmbedSettings
    compose: ComposeSettings
    retrieval: RetrievalSettings
    gate: GateSettings
    intents: Mapping[str, tuple[str, ...]]
    intent_sections: Mapping[str, tuple[str, ...]]
    demo_staff_username: str

    @property
    def endpoint(self) -> str:
        """Model server base URL (env override applied, no trailing slash)."""
        return self.serving.endpoint

    @property
    def records_dir(self) -> Path:
        """Absolute directory of ``<procedure_id>.json`` records."""
        return self.kb.records_dir

    @property
    def index_dir(self) -> Path:
        """Absolute directory of ``chunks.jsonl``, ``vectors.f32`` and ``index_meta.json``."""
        return self.kb.index_dir

    @property
    def embed_model_id(self) -> str:
        """Registry id of the embedding model (e.g. ``BAAI/bge-m3``)."""
        return self.embed.model_id

    @property
    def embed_serving_name(self) -> str:
        """Name of the embedding model on the local server (e.g. ``bge-m3``)."""
        return self.embed.serving_name

    @property
    def compose_model_id(self) -> str:
        """Registry id of the composer model (e.g. ``Qwen/Qwen3.5-2B``)."""
        return self.compose.model_id

    @property
    def compose_serving_name(self) -> str:
        """Name of the composer model on the local server (``compose.serving_name``)."""
        return self.compose.serving_name


def _absolute(root: Path, relative: str) -> Path:
    """Resolve a config-relative path against the repository root."""
    return (root / relative).resolve()


def _resolve_endpoint(serving: Mapping[str, Any]) -> str:
    """Return the env override of the endpoint when set and valid, else the file value."""
    env_name = str(serving["endpoint_env"])
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return str(serving["endpoint"]).rstrip("/")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ConfigError(
            f"Biến {env_name} phải là địa chỉ http(s)://máy:cổng của máy chủ model.",
            {"env": env_name},
        )
    return raw.rstrip("/")


def _ollama_options(serving: Mapping[str, Any]) -> Mapping[str, int]:
    """File ``ollama_options`` with ``num_gpu`` overridden by ``num_gpu_env`` when set."""
    options = {str(k): int(v) for k, v in (serving.get("ollama_options") or {}).items()}
    env_name = serving.get("num_gpu_env")
    raw = os.environ.get(str(env_name), "").strip() if env_name else ""
    if raw:
        if not raw.isdigit():
            raise ConfigError(
                f"Biến {env_name} phải là số nguyên ≥ 0 (0 = chỉ chạy CPU).", {"env": env_name}
            )
        options["num_gpu"] = int(raw)
    return MappingProxyType(options)


def _serving(serving: Mapping[str, Any]) -> ServingSettings:
    env = serving.get("num_gpu_env")
    return ServingSettings(
        endpoint=_resolve_endpoint(serving),
        endpoint_env=str(serving["endpoint_env"]),
        timeout_s=float(serving["timeout_s"]),
        num_gpu_env=str(env) if env else None,
        ollama_options=_ollama_options(serving),
    )


def _model_id(models: Mapping[str, Any], block: Mapping[str, Any], aliases: list) -> str:
    """Resolve ``block.model_ref`` to a registry id and check its serving-name alias."""
    ref = str(block["model_ref"])
    if ref not in models:
        raise ConfigError(
            f"config/rag.yaml tham chiếu model '{ref}' không có trong config/models.yaml.",
            {"model_ref": ref},
        )
    model_id = str(models[ref]["id"])
    names = {n for a in aliases if a["model_id"] == model_id for n in a["names"]}
    if block["serving_name"] not in names:
        raise ConfigError(
            f"Tên phục vụ '{block['serving_name']}' không phải bí danh của {model_id} "
            "trong serving_aliases (đổi model là điểm dừng, phải sửa config/models.yaml).",
            {"model_ref": ref, "model_id": model_id},
        )
    return model_id


def _compose(root: Path, block: Mapping[str, Any], model_id: str) -> ComposeSettings:
    prompt = str(block["prompt"])
    prompt_path = root.joinpath(*PROMPTS_SUBDIR, f"{prompt}.md")
    if not prompt_path.is_file():
        raise ConfigError(f"Thiếu file prompt {prompt}.md trong config/prompts.")
    return ComposeSettings(
        model_ref=str(block["model_ref"]),
        model_id=model_id,
        serving_name=str(block["serving_name"]),
        api=str(block["api"]),
        max_output_tokens=int(block["max_output_tokens"]),
        temperature=float(block["temperature"]),
        think=bool(block["think"]),
        keep_alive=str(block["keep_alive"]),
        prompt=prompt,
        prompt_path=prompt_path,
    )


def _retrieval(block: Mapping[str, Any]) -> RetrievalSettings:
    return RetrievalSettings(
        top_k=int(block["top_k"]),
        context_chunks=int(block["context_chunks"]),
        context_chars_per_chunk=int(block["context_chars_per_chunk"]),
        chunk_max_chars=int(block["chunk_max_chars"]),
        rrf_k=int(block["rrf_k"]),
        bm25_k1=float(block["bm25_k1"]),
        bm25_b=float(block["bm25_b"]),
        accent_fold=bool(block["accent_fold"]),
        synonyms=tuple(tuple(group) for group in block["synonyms"]),
        dialect_phrases=tuple((str(src), str(dst)) for src, dst in block["dialect_phrases"]),
    )


def _gate(block: Mapping[str, Any]) -> GateSettings:
    return GateSettings(
        min_dense_score=float(block["min_dense_score"]),
        high_dense_score=float(block["high_dense_score"]),
        title_overlap_min=float(block["title_overlap_min"]),
        lexical_min_support=float(block["lexical_min_support"]),
        confidence_weight_dense=float(block["confidence_weight_dense"]),
        generic_words=tuple(block["generic_words"]),
        out_of_scope_phrases=tuple(block.get("out_of_scope_phrases", ())),
        document_markers=tuple(block.get("document_markers", ())),
    )


def _frozen_lists(mapping: Mapping[str, list[str]]) -> Mapping[str, tuple[str, ...]]:
    """Read-only copy of ``{key: [str]}`` keeping key order."""
    return MappingProxyType({key: tuple(values) for key, values in mapping.items()})


def load_rag_settings(root: Path | None = None) -> RagSettings:
    """Load ``config/rag.yaml`` + ``config/models.yaml`` and resolve them (see module doc).

    Args:
        root: Repository root; defaults to :func:`ctcv_core.config.find_repo_root`.

    Raises:
        ConfigError: invalid file, unknown model, alias mismatch, missing prompt or bad
            endpoint override.
    """
    base = (root or find_repo_root()).resolve()
    cfg = load_config("rag", root=base)
    models = load_config("models", root=base)["models"]
    aliases = cfg["serving_aliases"]
    kb, serving, embed = cfg["kb"], cfg["serving"], cfg["embed"]
    return RagSettings(
        root=base,
        compose_mode=str(cfg["compose_mode"]),
        kb=KbSettings(
            records_dir=_absolute(base, kb["records_dir"]),
            index_dir=_absolute(base, kb["index_dir"]),
            skill=str(kb["skill"]),
            source_portal=str(kb["source_portal"]),
        ),
        serving=_serving(serving),
        embed=EmbedSettings(
            model_ref=str(embed["model_ref"]),
            model_id=_model_id(models, embed, aliases),
            serving_name=str(embed["serving_name"]),
            batch_size=int(embed["batch_size"]),
        ),
        compose=_compose(base, cfg["compose"], _model_id(models, cfg["compose"], aliases)),
        retrieval=_retrieval(cfg["retrieval"]),
        gate=_gate(cfg["gate"]),
        intents=_frozen_lists(cfg["intents"]),
        intent_sections=_frozen_lists(cfg["intent_sections"]),
        demo_staff_username=str(cfg["demo"]["staff_username"]),
    )
