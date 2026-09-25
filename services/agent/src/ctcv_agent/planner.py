"""Planner clients: vLLM (OpenAI-compatible, JSON mode) and a cassette replay for tests.

The planner is the only model with tools (``config/models.yaml: tools_allowed``). Its
identity, endpoint and output budget come from ``config/models.yaml``; ``VLLM_BASE_URL``
(the ``endpoint_env`` of the entry) overrides the endpoint at runtime (brief D29).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

import httpx
from pydantic import ValidationError

from ctcv_agent.schemas import PlannerOutput
from ctcv_core.config import find_repo_root, load_config
from ctcv_core.errors import AppError

DEFAULT_TIMEOUT_S = 30.0
TIMEOUT_ENV = "VLLM_TIMEOUT_S"
MODEL_KEY_ENV = "CTCV_PLANNER_MODEL"
PROFILES_ENV = "COMPOSE_PROFILES"
CHAT_PATH = "/chat/completions"
CASSETTE_DIRNAME = ("services", "agent", "tests", "cassettes")
_FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class Message(TypedDict):
    """One chat message (OpenAI-compatible shape)."""

    role: Literal["system", "user", "assistant"]
    content: str


class PlannerClient(Protocol):
    """Anything that turns a message list into a validated :class:`PlannerOutput`."""

    def complete(self, messages: Sequence[Message]) -> PlannerOutput:
        """Return the planner's structured reply; raise :class:`PlannerError` on failure."""
        ...


class PlannerError(AppError):
    """The planner could not be reached or returned something that is not a PlannerOutput."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        """Build a 502 ``PLANNER_ERROR`` (Vietnamese message); ``reason`` is machine-readable."""
        super().__init__(
            "PLANNER_ERROR",
            "Trợ lý đang bận một chút, cháu sẽ nhờ tình nguyện viên giúp bác nhé.",
            502,
            {"reason": reason, **(details or {})},
        )
        self.reason = reason


class CassetteMissingError(PlannerError):
    """No recorded cassette matches the messages — tests never fall back to the network."""


# ----------------------------------------------------------------------------- config
@dataclass(frozen=True)
class PlannerModel:
    """Resolved planner settings from ``config/models.yaml`` plus environment overrides."""

    key: str
    model_id: str
    base_url: str
    max_output_tokens: int
    timeout_s: float
    prompt: str


def default_model_key() -> str:
    """``planner`` on the GPU profile, ``planner_small`` on the CPU path (brief D29).

    ``CTCV_PLANNER_MODEL`` wins when set; otherwise ``COMPOSE_PROFILES`` containing ``cpu``
    (and not ``gpu``) selects the small model served by llama.cpp.
    """
    explicit = os.environ.get(MODEL_KEY_ENV, "").strip()
    if explicit:
        return explicit
    profiles = {p.strip() for p in os.environ.get(PROFILES_ENV, "").split(",") if p.strip()}
    if "cpu" in profiles and "gpu" not in profiles:
        return "planner_small"
    return "planner"


def planner_model(key: str | None = None) -> PlannerModel:
    """Read the planner entry ``key`` (default :func:`default_model_key`) from config."""
    chosen = key or default_model_key()
    models = load_config("models")["models"]
    if chosen not in models or not models[chosen].get("tools_allowed"):
        raise PlannerError("model_not_a_planner", {"key": chosen})
    entry = models[chosen]
    env_name = entry.get("endpoint_env") or ""
    base_url = os.environ.get(env_name, "").strip() if env_name else ""
    timeout_raw = os.environ.get(TIMEOUT_ENV) or entry.get("timeout_s") or DEFAULT_TIMEOUT_S
    return PlannerModel(
        key=chosen,
        model_id=entry["id"],
        base_url=(base_url or entry["endpoint"]).rstrip("/"),
        max_output_tokens=int(entry.get("max_output_tokens", 160)),
        timeout_s=float(timeout_raw),
        prompt=entry.get("prompt", "coach.v1"),
    )


@lru_cache(maxsize=4)
def load_system_prompt(name: str) -> str:
    """Body of ``config/prompts/<name>.md`` without its YAML front matter."""
    path = find_repo_root() / "config" / "prompts" / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    return _FRONT_MATTER_RE.sub("", text, count=1).strip()


# ----------------------------------------------------------------------------- parsing
def parse_planner_output(text: str) -> PlannerOutput:
    """Parse the model's JSON reply strictly into :class:`PlannerOutput`.

    Code fences and leading/trailing prose are tolerated; anything that does not
    validate raises :class:`PlannerError` (the coach then says a safe line and escalates).
    """
    body = _FENCE_RE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        raise PlannerError("no_json_object")
    try:
        data = json.loads(body[start : end + 1])
    except json.JSONDecodeError as exc:
        raise PlannerError("invalid_json", {"position": exc.pos}) from None
    try:
        return PlannerOutput.model_validate(data)
    except ValidationError as exc:
        locs = [".".join(str(p) for p in e["loc"]) or "(root)" for e in exc.errors()]
        raise PlannerError("schema_mismatch", {"fields": locs}) from None


def _extract_content(payload: Any) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise PlannerError("bad_response_shape") from None
    if not isinstance(content, str):
        raise PlannerError("bad_response_shape")
    return content


# ----------------------------------------------------------------------------- clients
class VllmClient:
    """Chat-completions client for vLLM / llama.cpp (OpenAI-compatible) in JSON mode."""

    def __init__(
        self,
        model: PlannerModel | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Bind to ``model`` (default: from config); ``transport`` lets tests stub HTTP."""
        self.model = model or planner_model()
        self._client = httpx.Client(
            base_url=self.model.base_url, timeout=self.model.timeout_s, transport=transport
        )

    def request_body(self, messages: Sequence[Message]) -> dict[str, Any]:
        """The JSON body sent to ``/chat/completions``."""
        return {
            "model": self.model.model_id,
            "messages": list(messages),
            "temperature": 0,
            "max_tokens": self.model.max_output_tokens,
            "response_format": {"type": "json_object"},
        }

    def complete(self, messages: Sequence[Message]) -> PlannerOutput:
        """POST the messages and parse the reply."""
        try:
            response = self._client.post(CHAT_PATH, json=self.request_body(messages))
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise PlannerError("http_status", {"status": exc.response.status_code}) from None
        except httpx.HTTPError as exc:
            raise PlannerError("http_error", {"kind": type(exc).__name__}) from None
        except ValueError:
            raise PlannerError("invalid_json") from None
        return parse_planner_output(_extract_content(payload))

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()


def cassette_key(messages: Sequence[Message]) -> str:
    """SHA-256 of the canonical JSON of ``messages`` (the cassette lookup key)."""
    canonical = json.dumps(
        list(messages), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_cassette_dir() -> Path:
    """``services/agent/tests/cassettes`` under the repository root."""
    return find_repo_root().joinpath(*CASSETTE_DIRNAME)


def write_cassette(
    path: Path, name: str, messages: Sequence[Message], output: PlannerOutput
) -> None:
    """Write a cassette file ``{name, sha256, messages, response}`` (used by make_cassettes.py)."""
    payload = {
        "name": name,
        "sha256": cassette_key(messages),
        "messages": list(messages),
        "response": output.model_dump(mode="json"),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


class ReplayClient:
    """Planner that replays recorded cassettes; a miss raises :class:`CassetteMissingError`."""

    def __init__(self, cassette_dir: Path | None = None) -> None:
        """Load every ``*.json`` cassette in ``cassette_dir`` (default: the tests folder)."""
        self.cassette_dir = cassette_dir or default_cassette_dir()
        self._responses: dict[str, tuple[str, PlannerOutput]] = {}
        for path in sorted(self.cassette_dir.glob("*.json")):
            self._load(path)

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        key = cassette_key(data["messages"])
        recorded = data.get("sha256")
        if recorded and recorded != key:
            raise PlannerError("cassette_stale", {"file": path.name, "expected": key})
        self._responses[key] = (
            data.get("name", path.stem),
            PlannerOutput.model_validate(data["response"]),
        )

    def add(self, messages: Sequence[Message], output: PlannerOutput, name: str = "inline") -> str:
        """Register an in-memory cassette and return its key."""
        key = cassette_key(messages)
        self._responses[key] = (name, output)
        return key

    @property
    def names(self) -> list[str]:
        """Names of the loaded cassettes."""
        return sorted(name for name, _ in self._responses.values())

    def complete(self, messages: Sequence[Message]) -> PlannerOutput:
        """Return the recorded reply for ``messages`` or fail loudly — never hit the network."""
        key = cassette_key(messages)
        hit = self._responses.get(key)
        if hit is None:
            raise CassetteMissingError(
                "cassette_missing",
                {
                    "sha256": key,
                    "cassette_dir": str(self.cassette_dir),
                    "available": self.names,
                    "hint": "uv run python services/agent/tests/make_cassettes.py",
                },
            )
        return hit[1].model_copy(deep=True)
