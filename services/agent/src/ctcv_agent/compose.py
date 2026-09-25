"""Sentence composers for TTHC answers (ADR-007): one sentence from retrieved chunks, no tools.

A composer turns ``(question, chunks)`` into at most one Vietnamese sentence plus the ids of
the chunks it used. It has **no tool** and its output is never trusted: the answer engine
(:mod:`ctcv_agent.ask`) checks every number and word against the cited chunks and falls back
to a deterministic template when the check fails. A composer never raises: transport,
decoding and format problems come back as ``ComposeOutput.error`` (a short machine code, no
question text).

* :class:`OllamaComposer` — ``POST {endpoint}/api/chat`` (``compose.api: ollama_chat``);
* :class:`OpenAICompatComposer` — ``POST {endpoint}/v1/chat/completions`` (vLLM, llama.cpp);
* :class:`FakeComposer` — scripted replies for tests.

The system prompt is the body of ``config/prompts/<compose.prompt>.md``; the user message is
the (PII-redacted) question followed by every chunk wrapped in
``<<<NGUON id=DOC_ID>>> … <<<HET>>>`` and cut to ``retrieval.context_chars_per_chunk``.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlsplit

import httpx

from ctcv_agent.guardrails import redact_pii
from ctcv_agent.planner import load_system_prompt
from ctcv_agent.rag.settings import RagSettings
from ctcv_agent.rag.types import Chunk

NOT_SURE_TOKEN = "KHONG_CHAC"
SOURCE_OPEN = "<<<NGUON id={doc_id}>>>"
SOURCE_CLOSE = "<<<HET>>>"
_MARKER_RE = re.compile(r"<<<[^<>]{0,80}>>>|<<<|>>>")
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"^.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?", re.IGNORECASE)

Parsed = tuple[str | None, tuple[str, ...], bool, str | None]


@dataclass(frozen=True)
class ComposeOutput:
    """One composer reply.

    Attributes:
        sentence: The proposed answer sentence, or None (``KHONG_CHAC`` or failure).
        doc_ids: Ids of the chunks the model says it used (unverified).
        raw_ok: True when the reply was valid JSON of the expected shape.
        error: Short machine code when the call or the parsing failed, else None.
        latency_ms: Wall time of the call in milliseconds.
    """

    sentence: str | None
    doc_ids: tuple[str, ...]
    raw_ok: bool
    error: str | None
    latency_ms: float


@runtime_checkable
class Composer(Protocol):
    """Anything that proposes one answer sentence from retrieved chunks."""

    @property
    def hosts_contacted(self) -> list[str]:
        """``host:port`` of every server this composer sent a request to."""
        ...

    def compose(self, question: str, chunks: Sequence[Chunk]) -> ComposeOutput:
        """Return a :class:`ComposeOutput`; never raise."""
        ...


# ----------------------------------------------------------------------------- parsing
def _strip_reasoning(text: str) -> str:
    """Remove ``<think>…</think>`` blocks (and anything before a dangling ``</think>``)."""
    text = _THINK_BLOCK_RE.sub("", text)
    return _THINK_CLOSE_RE.sub("", text, count=1).strip()


def _doc_ids(value: Any) -> tuple[str, ...]:
    """Distinct string ids in order; anything that is not a list gives ``()``."""
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(v.strip() for v in value if isinstance(v, str) and v.strip()))


def parse_compose_reply(text: str) -> Parsed:
    """Parse ``{"answer", "doc_ids"}`` from raw model text.

    Returns:
        ``(sentence, doc_ids, raw_ok, error)``; ``sentence`` is None for ``KHONG_CHAC``
        (``raw_ok`` True, no error) and for every failure (``raw_ok`` False, ``error`` set).
    """
    body = _FENCE_RE.sub("", _strip_reasoning(text or ""))
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None, (), False, "no_json_object"
    try:
        data = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return None, (), False, "invalid_json"
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        return None, (), False, "bad_shape"
    answer = " ".join(data["answer"].split())
    if not answer:
        return None, (), False, "empty_answer"
    if answer == NOT_SURE_TOKEN:
        return None, (), True, None
    return answer, _doc_ids(data.get("doc_ids")), True, None


# ----------------------------------------------------------------------------- messages
def _clean(text: str) -> str:
    """Remove block markers so untrusted text cannot open or close a source block."""
    return _MARKER_RE.sub(" ", text)


def build_user_message(question: str, chunks: Sequence[Chunk], chars_per_chunk: int) -> str:
    """User message: redacted question, then each chunk in its source block."""
    blocks = [
        f"{SOURCE_OPEN.format(doc_id=c.doc_id)}\n{_clean(c.text)[:chars_per_chunk]}\n{SOURCE_CLOSE}"
        for c in chunks
    ]
    question_line = " ".join(_clean(redact_pii(question)).split())
    return "\n\n".join([f"CÂU HỎI: {question_line}", *blocks])


class _HttpComposer:
    """Shared HTTP plumbing: message building, timing, error mapping, host tracking."""

    path = ""

    def __init__(
        self, settings: RagSettings, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        """Bind to the endpoint and model of ``settings``; no request is made here."""
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.endpoint, timeout=settings.serving.timeout_s, transport=transport
        )
        self._host = urlsplit(settings.endpoint).netloc
        self._hosts: list[str] = []

    @property
    def hosts_contacted(self) -> list[str]:
        """``host:port`` of the model server once a request was attempted."""
        return list(self._hosts)

    def _messages(self, question: str, chunks: Sequence[Chunk]) -> list[dict[str, str]]:
        s = self._settings
        user = build_user_message(question, chunks, s.retrieval.context_chars_per_chunk)
        return [
            {"role": "system", "content": load_system_prompt(s.compose.prompt)},
            {"role": "user", "content": user},
        ]

    def request_body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """JSON body for the chat endpoint (overridden per API)."""
        raise NotImplementedError

    def extract_content(self, payload: Any) -> str:
        """Assistant text from the response payload (overridden per API)."""
        raise NotImplementedError

    def _call(self, messages: list[dict[str, str]]) -> str:
        if self._host not in self._hosts:
            self._hosts.append(self._host)
        response = self._client.post(self.path, json=self.request_body(messages))
        response.raise_for_status()
        return self.extract_content(response.json())

    def compose(self, question: str, chunks: Sequence[Chunk]) -> ComposeOutput:
        """Call the model once and parse its reply; every failure becomes ``error``."""
        started = time.perf_counter()
        try:
            text = self._call(self._messages(question, chunks))
            sentence, doc_ids, raw_ok, error = parse_compose_reply(text)
        except Exception as exc:  # noqa: BLE001 — a composer must never raise
            sentence, doc_ids, raw_ok, error = None, (), False, _error_code(exc)
        elapsed = (time.perf_counter() - started) * 1000.0
        return ComposeOutput(sentence, doc_ids, raw_ok, error, round(elapsed, 3))

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


class _BadResponseError(Exception):
    """The server answered with JSON of an unexpected shape."""


def _error_code(exc: Exception) -> str:
    """Short, PII-free code for a failed call."""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_status:{exc.response.status_code}"
    if isinstance(exc, httpx.HTTPError):
        return f"http_error:{type(exc).__name__}"
    if isinstance(exc, _BadResponseError):
        return "bad_response_shape"
    if isinstance(exc, ValueError):
        return "invalid_response"
    return f"unexpected:{type(exc).__name__}"


class OllamaComposer(_HttpComposer):
    """Composer on Ollama's native chat API (JSON format, thinking off)."""

    path = "/api/chat"

    def request_body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Body of ``POST /api/chat`` built from ``config/rag.yaml: compose``."""
        c = self._settings.compose
        return {
            "model": self._settings.compose_serving_name,
            "messages": messages,
            "stream": False,
            "think": c.think,
            "format": "json",
            "keep_alive": c.keep_alive,
            "options": {
                **self._settings.serving.ollama_options,
                "temperature": c.temperature,
                "num_predict": c.max_output_tokens,
            },
        }

    def extract_content(self, payload: Any) -> str:
        """``payload["message"]["content"]``."""
        try:
            content = payload["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise _BadResponseError from None
        if not isinstance(content, str):
            raise _BadResponseError
        return content


class OpenAICompatComposer(_HttpComposer):
    """Composer on an OpenAI-compatible server (vLLM, llama.cpp, Ollama ``/v1``)."""

    path = "/v1/chat/completions"

    def request_body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Body of ``POST /v1/chat/completions`` in JSON mode with thinking disabled."""
        c = self._settings.compose
        return {
            "model": self._settings.compose_serving_name,
            "messages": messages,
            "temperature": c.temperature,
            "max_tokens": c.max_output_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": c.think},
        }

    def extract_content(self, payload: Any) -> str:
        """``payload["choices"][0]["message"]["content"]``."""
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise _BadResponseError from None
        if not isinstance(content, str):
            raise _BadResponseError
        return content


_COMPOSERS: dict[str, type[_HttpComposer]] = {
    "ollama_chat": OllamaComposer,
    "openai_chat": OpenAICompatComposer,
}


def build_composer(
    settings: RagSettings, *, transport: httpx.BaseTransport | None = None
) -> Composer:
    """Composer for ``compose.api`` of ``settings``.

    Raises:
        ValueError: when ``compose.api`` names no known API.
    """
    api = settings.compose.api
    if api not in _COMPOSERS:
        raise ValueError(f"compose.api không hỗ trợ: {api!r} (chỉ {', '.join(_COMPOSERS)})")
    return _COMPOSERS[api](settings, transport=transport)


# ----------------------------------------------------------------------------- tests
class FakeComposer:
    """Scripted composer for tests: replays outputs in order, then repeats the last one.

    Each scripted item is raw model text (parsed like a real reply), a ready
    :class:`ComposeOutput`, or an exception to raise. Calls are recorded in ``calls`` as
    ``(question, chunks)``.
    """

    def __init__(self, scripted: Sequence[str | ComposeOutput | Exception] | str) -> None:
        """Store the script (a single string is a one-item script)."""
        items = [scripted] if isinstance(scripted, str) else list(scripted)
        if not items:
            raise ValueError("FakeComposer cần ít nhất một câu trả lời mẫu")
        self._items = items
        self.calls: list[tuple[str, list[Chunk]]] = []

    @property
    def hosts_contacted(self) -> list[str]:
        """A fake composer contacts no host."""
        return []

    def compose(self, question: str, chunks: Sequence[Chunk]) -> ComposeOutput:
        """Record the call and return (or raise) the next scripted item."""
        self.calls.append((question, list(chunks)))
        item = self._items.pop(0) if len(self._items) > 1 else self._items[0]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ComposeOutput):
            return item
        sentence, doc_ids, raw_ok, error = parse_compose_reply(item)
        return ComposeOutput(sentence, doc_ids, raw_ok, error, 0.0)
