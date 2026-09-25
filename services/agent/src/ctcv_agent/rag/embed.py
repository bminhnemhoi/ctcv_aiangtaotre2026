"""Text embedders for the TTHC index: the local Ollama server and a deterministic test double.

* :class:`OllamaEmbedder` — ``POST {endpoint}/api/embed`` with the served name of the
  embedding model (``config/rag.yaml: embed.serving_name``, an alias of the registry id in
  ``config/models.yaml``). Endpoint, batch size and timeout come from
  :func:`~ctcv_agent.rag.settings.load_rag_settings` (``CTCV_OLLAMA_BASE_URL`` overrides the
  endpoint). Every failure becomes :class:`EmbedderUnavailable` (503); the hosts actually
  contacted are listed in ``hosts_contacted`` so evaluation can prove no external call.
* :class:`HashEmbedder` — feature hashing of accent-free words; deterministic, no
  model, used by unit tests and the performance test.

Vectors are always returned L2-normalised, so cosine similarity is a plain dot product.
This module is not an agent tool; tools never import it (they read ``GuideIndex``).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from types import TracebackType
from typing import Any, Protocol, Self, runtime_checkable
from urllib.parse import urlsplit

import httpx

from ctcv_agent.rag.query import content_tokens, fold_accents
from ctcv_agent.rag.settings import RagSettings, load_rag_settings
from ctcv_core.errors import AppError

EMBED_PATH = "/api/embed"
_DEFAULT_PORTS = {"http": 80, "https": 443}


@runtime_checkable
class Embedder(Protocol):
    """Anything that turns texts into L2-normalised vectors of one fixed dimension."""

    model_id: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one normalised vector per text, in input order."""
        ...


class EmbedderUnavailable(AppError):  # noqa: N818 — name fixed by ADR-007 C4
    """503 — the embedding server could not be reached or answered something unusable."""

    CODE = "EMBEDDER_UNAVAILABLE"
    STATUS = 503
    MESSAGE = "Máy tra cứu đang bận, bác thử lại sau ít phút nhé."

    def __init__(self, reason: str | None = None) -> None:
        """Create the error; ``reason`` (an error class or check name, never text) → details."""
        details = {"reason": reason} if reason else None
        super().__init__(self.CODE, self.MESSAGE, self.STATUS, details)


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return ``vector`` scaled to unit length.

    Raises:
        ValueError: for an empty, zero or non-finite vector.
    """
    norm = math.sqrt(math.fsum(float(v) * float(v) for v in vector))
    if not vector or not math.isfinite(norm) or norm == 0.0:
        raise ValueError("vector rỗng, bằng 0 hoặc không hữu hạn")
    return [float(v) / norm for v in vector]


def _host_port(endpoint: str) -> str:
    """``host:port`` of an http(s) URL, filling in the scheme's default port."""
    parts = urlsplit(endpoint)
    port = parts.port or _DEFAULT_PORTS.get(parts.scheme, 0)
    return f"{parts.hostname}:{port}"


def _is_number(value: Any) -> bool:
    """True for finite ints/floats (bools excluded)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return math.isfinite(value)


def _checked_vectors(payload: Any, expected: int) -> list[list[float]]:
    """Validate an ``/api/embed`` answer and return its normalised vectors."""
    vectors = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(vectors, list) or len(vectors) != expected:
        raise EmbedderUnavailable("bad_shape")
    dims = {len(v) if isinstance(v, list) else -1 for v in vectors}
    if len(dims) != 1 or min(dims) < 1:
        raise EmbedderUnavailable("bad_shape")
    if not all(_is_number(x) for v in vectors for x in v):
        raise EmbedderUnavailable("bad_shape")
    try:
        return [l2_normalize(v) for v in vectors]
    except ValueError as exc:
        raise EmbedderUnavailable("zero_vector") from exc


class OllamaEmbedder:
    """Embeddings from the local Ollama server (see module docstring).

    Args:
        settings: Resolved RAG settings; loaded from ``config/rag.yaml`` when omitted.
        transport: Optional httpx transport (tests pass ``httpx.MockTransport``).
    """

    def __init__(
        self, settings: RagSettings | None = None, transport: httpx.BaseTransport | None = None
    ) -> None:
        """Read endpoint, model names, batch size and timeout; no request is made here."""
        resolved = settings or load_rag_settings()
        self.model_id: str = resolved.embed_model_id
        self.serving_name: str = resolved.embed_serving_name
        self.endpoint: str = resolved.endpoint
        self.batch_size: int = max(1, resolved.embed.batch_size)
        self.options: dict[str, int] = dict(resolved.serving.ollama_options)
        self.hosts_contacted: list[str] = []
        self._url = f"{self.endpoint}{EMBED_PATH}"
        self._client = httpx.Client(
            transport=transport, timeout=httpx.Timeout(resolved.serving.timeout_s)
        )

    @property
    def closed(self) -> bool:
        """True once :meth:`close` has run."""
        return self._client.is_closed

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> Self:
        """Use as a context manager that closes the client on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client."""
        self.close()

    def _note_host(self) -> None:
        host = _host_port(self.endpoint)
        if host not in self.hosts_contacted:
            self.hosts_contacted.append(host)

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """One ``/api/embed`` call; every failure is mapped to :class:`EmbedderUnavailable`."""
        self._note_host()
        try:
            body: dict[str, object] = {"model": self.serving_name, "input": batch}
            if self.options:
                body["options"] = self.options  # e.g. num_gpu=0 for a CPU-only run
            response = self._client.post(self._url, json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbedderUnavailable(type(exc).__name__) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbedderUnavailable("bad_json") from exc
        return _checked_vectors(payload, len(batch))

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed ``texts`` in batches of ``embed.batch_size``; empty input makes no request.

        Raises:
            EmbedderUnavailable: network error, HTTP error or malformed answer.
        """
        items = list(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(items), self.batch_size):
            vectors.extend(self._embed_batch(items[start : start + self.batch_size]))
        return vectors


class HashEmbedder:
    """Deterministic feature hashing of accent-free content words (tests only).

    Texts sharing words get similar vectors; accents are ignored. A text without content
    words hashes its raw form, so every vector is non-zero and unit length.

    Args:
        dim: Vector dimension (≥ 1).
        model_id: Identity recorded in ``index_meta.json``; defaults to
            ``ctcv/hash-embedder-<dim>``.
    """

    serving_name: str | None = None

    def __init__(self, dim: int = 64, *, model_id: str | None = None) -> None:
        """Set the dimension and identity."""
        if dim < 1:
            raise ValueError(f"dim phải ≥ 1, nhận được {dim}")
        self.dim = dim
        self.model_id = model_id or f"ctcv/hash-embedder-{dim}"

    def _vector(self, text: str) -> list[float]:
        features = [fold_accents(token) for token in content_tokens(text)] or [text]
        vector = [0.0] * self.dim
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "little") % self.dim] += 1.0
        return l2_normalize(vector)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one unit vector per text."""
        return [self._vector(text) for text in texts]
