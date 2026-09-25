"""Embedders: OllamaEmbedder (config-driven endpoint, batching, L2) and HashEmbedder (tests)."""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Callable

import httpx
import pytest

from ctcv_agent.rag.embed import (
    Embedder,
    EmbedderUnavailable,
    HashEmbedder,
    OllamaEmbedder,
    l2_normalize,
)
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_core.config import clear_config_cache
from ctcv_core.errors import AppError

ENDPOINT_ENV = "CTCV_OLLAMA_BASE_URL"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> RagSettings:
    monkeypatch.delenv(ENDPOINT_ENV, raising=False)
    clear_config_cache()
    return load_rag_settings()


def _with_batch(settings: RagSettings, batch_size: int) -> RagSettings:
    return dataclasses.replace(
        settings, embed=dataclasses.replace(settings.embed, batch_size=batch_size)
    )


class Recorder:
    """MockTransport handler: answers /api/embed with deterministic vectors, logs requests."""

    def __init__(self, reply: Callable[[list[str]], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.bodies: list[dict] = []
        self._reply = reply

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        self.bodies.append(body)
        if self._reply is not None:
            return self._reply(body["input"])
        vectors = [[float(len(text)), 1.0, 0.0] for text in body["input"]]
        return httpx.Response(200, json={"model": body["model"], "embeddings": vectors})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def test_posts_to_configured_endpoint_with_serving_name(settings: RagSettings) -> None:
    rec = Recorder()
    embedder = OllamaEmbedder(settings, transport=rec.transport())
    vectors = embedder.embed(["lệ phí"])
    assert len(vectors) == 1
    request = rec.requests[0]
    assert request.method == "POST"
    assert str(request.url) == f"{settings.endpoint}/api/embed"
    assert rec.bodies[0] == {"model": settings.embed_serving_name, "input": ["lệ phí"]}
    assert embedder.model_id == settings.embed_model_id == "BAAI/bge-m3"
    assert embedder.serving_name == "bge-m3"
    assert embedder.hosts_contacted == ["localhost:11434"]


def test_endpoint_comes_from_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENDPOINT_ENV, "http://embed-box.test:9999/")
    clear_config_cache()
    rec = Recorder()
    embedder = OllamaEmbedder(load_rag_settings(), transport=rec.transport())
    embedder.embed(["a", "b"])
    assert str(rec.requests[0].url) == "http://embed-box.test:9999/api/embed"
    assert embedder.hosts_contacted == ["embed-box.test:9999"]


def test_default_settings_are_loaded_when_omitted(settings: RagSettings) -> None:
    rec = Recorder()
    embedder = OllamaEmbedder(transport=rec.transport())
    embedder.embed(["x"])
    assert str(rec.requests[0].url) == f"{settings.endpoint}/api/embed"


def test_batches_follow_config_batch_size_and_keep_order(settings: RagSettings) -> None:
    rec = Recorder()
    embedder = OllamaEmbedder(_with_batch(settings, 2), transport=rec.transport())
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    vectors = embedder.embed(texts)
    assert [len(b["input"]) for b in rec.bodies] == [2, 2, 1]
    assert [b["input"] for b in rec.bodies] == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    expected = [l2_normalize([float(len(t)), 1.0, 0.0]) for t in texts]
    assert len(vectors) == len(expected)
    for got, want in zip(vectors, expected, strict=True):
        assert got == pytest.approx(want)
    assert embedder.hosts_contacted == ["localhost:11434"]


def test_vectors_are_l2_normalised(settings: RagSettings) -> None:
    rec = Recorder(lambda texts: httpx.Response(200, json={"embeddings": [[3.0, 4.0]]}))
    [vector] = OllamaEmbedder(settings, transport=rec.transport()).embed(["x"])
    assert vector == pytest.approx([0.6, 0.8])
    assert math.fsum(v * v for v in vector) == pytest.approx(1.0)


def test_timeout_comes_from_config(settings: RagSettings) -> None:
    rec = Recorder()
    OllamaEmbedder(settings, transport=rec.transport()).embed(["x"])
    timeout = rec.requests[0].extensions["timeout"]
    assert timeout["read"] == settings.serving.timeout_s
    assert timeout["connect"] == settings.serving.timeout_s


def test_empty_input_makes_no_request(settings: RagSettings) -> None:
    rec = Recorder()
    embedder = OllamaEmbedder(settings, transport=rec.transport())
    assert embedder.embed([]) == []
    assert rec.requests == [] and embedder.hosts_contacted == []


def _json(payload: object, status: int = 200) -> Callable[[list[str]], httpx.Response]:
    return lambda texts: httpx.Response(status, json=payload)


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (_json({"error": "boom"}, 500), "HTTPStatusError"),
        (lambda texts: httpx.Response(200, content=b"not json"), "bad_json"),
        (_json({"embeddings": [[1.0, 0.0]]}), "bad_shape"),
        (_json({"embeddings": "nope"}), "bad_shape"),
        (_json(["not", "a", "dict"]), "bad_shape"),
        (_json({"embeddings": [[1.0, 0.0], [1.0]]}), "bad_shape"),
        (_json({"embeddings": [["a", 0.0], [1.0, 0.0]]}), "bad_shape"),
        (_json({"embeddings": [[0.0, 0.0], [1.0, 0.0]]}), "zero_vector"),
        (_json({"embeddings": [[], []]}), "bad_shape"),
        (_json({"embeddings": [[True, 1.0], [1.0, 0.0]]}), "bad_shape"),
    ],
)
def test_bad_responses_raise_embedder_unavailable(
    settings: RagSettings, reply: Callable[[list[str]], httpx.Response], reason: str
) -> None:
    rec = Recorder(reply)
    embedder = OllamaEmbedder(settings, transport=rec.transport())
    with pytest.raises(EmbedderUnavailable) as exc:
        embedder.embed(["a", "b"])
    assert exc.value.details == {"reason": reason}
    assert embedder.hosts_contacted == ["localhost:11434"]


def test_connection_error_raises_embedder_unavailable(settings: RagSettings) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    embedder = OllamaEmbedder(settings, transport=httpx.MockTransport(refuse))
    with pytest.raises(EmbedderUnavailable) as exc:
        embedder.embed(["a"])
    assert exc.value.details == {"reason": "ConnectError"}


def test_error_is_a_503_app_error_with_vietnamese_message() -> None:
    err = EmbedderUnavailable("ConnectError")
    assert isinstance(err, AppError)
    assert (err.code, err.status) == ("EMBEDDER_UNAVAILABLE", 503)
    body = err.to_response()["error"]
    assert body["code"] == "EMBEDDER_UNAVAILABLE"
    assert "bác" in body["message"] and "http" not in body["message"]
    assert EmbedderUnavailable().details is None


def test_close_releases_the_client(settings: RagSettings) -> None:
    rec = Recorder()
    with OllamaEmbedder(settings, transport=rec.transport()) as embedder:
        embedder.embed(["a"])
    assert embedder.closed


def test_l2_normalize_rejects_zero_and_non_finite() -> None:
    assert l2_normalize([0.0, 2.0]) == [0.0, 1.0]
    with pytest.raises(ValueError):
        l2_normalize([0.0, 0.0])
    with pytest.raises(ValueError):
        l2_normalize([float("nan"), 1.0])
    with pytest.raises(ValueError):
        l2_normalize([])


# ----------------------------------------------------------------------------- HashEmbedder
def test_hash_embedder_is_deterministic_and_unit_length() -> None:
    first = HashEmbedder(dim=64).embed(["Lệ phí đăng ký thường trú", ""])
    second = HashEmbedder(dim=64).embed(["Lệ phí đăng ký thường trú", ""])
    assert first == second
    for vector in first:
        assert len(vector) == 64
        assert math.fsum(v * v for v in vector) == pytest.approx(1.0)


def _cos(a: list[float], b: list[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def test_hash_embedder_similarity_follows_shared_words() -> None:
    emb = HashEmbedder(dim=256)
    query, near, far = emb.embed(
        ["lệ phí thường trú", "Lệ phí đăng ký thường trú 20.000 đồng", "Cấp hộ chiếu phổ thông"]
    )
    assert _cos(query, near) > _cos(query, far)


def test_hash_embedder_ignores_diacritics() -> None:
    emb = HashEmbedder(dim=64)
    accented, plain = emb.embed(["lệ phí thường trú", "le phi thuong tru"])
    assert accented == plain


def test_hash_embedder_identity_and_validation() -> None:
    emb = HashEmbedder(dim=1024)
    assert emb.dim == 1024 and emb.model_id == "ctcv/hash-embedder-1024"
    assert HashEmbedder(dim=8, model_id="test/x").model_id == "test/x"
    assert isinstance(emb, Embedder) and isinstance(HashEmbedder(), Embedder)
    assert HashEmbedder().dim == 64
    assert emb.embed([]) == []
    with pytest.raises(ValueError):
        HashEmbedder(dim=0)


def test_ollama_options_are_sent_with_embed_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    # v2: CTCV_OLLAMA_NUM_GPU=0 keeps bge-m3 on the CPU too.
    monkeypatch.setenv("CTCV_OLLAMA_NUM_GPU", "0")
    clear_config_cache()
    rec = Recorder()
    OllamaEmbedder(load_rag_settings(), transport=rec.transport()).embed(["a"])
    assert rec.bodies[0]["options"] == {"num_gpu": 0}
