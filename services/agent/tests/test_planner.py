"""Planner clients: config resolution, strict parsing, vLLM transport errors, replay cassettes."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ctcv_agent.planner import (
    CassetteMissingError,
    Message,
    PlannerError,
    PlannerModel,
    ReplayClient,
    VllmClient,
    cassette_key,
    default_cassette_dir,
    default_model_key,
    load_system_prompt,
    parse_planner_output,
    planner_model,
    write_cassette,
)
from ctcv_agent.schemas import PlannerOutput

GOOD = {
    "say": "Bác bấm nút xanh có chữ Quét QR nhé.",
    "action_hint": None,
    "tool_calls": [],
    "confidence": 0.9,
}
MESSAGES: list[Message] = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


# ----------------------------------------------------------------------------- config
def test_default_model_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CTCV_PLANNER_MODEL", raising=False)
    monkeypatch.setenv("COMPOSE_PROFILES", "cpu")
    assert default_model_key() == "planner_small"
    monkeypatch.setenv("COMPOSE_PROFILES", "cpu,gpu")
    assert default_model_key() == "planner"
    monkeypatch.delenv("COMPOSE_PROFILES")
    assert default_model_key() == "planner"
    monkeypatch.setenv("CTCV_PLANNER_MODEL", "planner_small")
    assert default_model_key() == "planner_small"


def test_planner_model_from_config_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    monkeypatch.delenv("VLLM_TIMEOUT_S", raising=False)
    model = planner_model("planner")
    assert model.model_id == "Qwen/Qwen3.5-9B"
    assert model.base_url == "http://models:8040/v1"
    assert model.prompt == "coach.v1" and model.max_output_tokens == 160 and model.timeout_s == 30.0
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:9999/v1/")
    monkeypatch.setenv("VLLM_TIMEOUT_S", "5")
    model = planner_model("planner")
    assert model.base_url == "http://127.0.0.1:9999/v1" and model.timeout_s == 5.0


def test_planner_model_rejects_non_planner() -> None:
    with pytest.raises(PlannerError) as exc:
        planner_model("quarantine")
    assert exc.value.reason == "model_not_a_planner"


def test_system_prompt_strips_front_matter() -> None:
    body = load_system_prompt("coach.v1")
    assert not body.startswith("---")
    assert "PlannerOutput" in body and "2 câu" in body


# ----------------------------------------------------------------------------- parsing
@pytest.mark.parametrize(
    "text",
    [
        json.dumps(GOOD, ensure_ascii=False),
        "```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```",
        "Đây là kết quả: " + json.dumps(GOOD, ensure_ascii=False) + " xong.",
    ],
)
def test_parse_planner_output_tolerates_fences(text: str) -> None:
    assert parse_planner_output(text).confidence == 0.9


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("không có json", "no_json_object"),
        ("{say: nope}", "invalid_json"),
        ('{"say": "x", "confidence": 2}', "schema_mismatch"),
        (
            '{"say": "x", "confidence": 0.5, "tool_calls": [{"name": "x", "args": 1}]}',
            "schema_mismatch",
        ),
    ],
)
def test_parse_planner_output_strict(text: str, reason: str) -> None:
    with pytest.raises(PlannerError) as exc:
        parse_planner_output(text)
    assert exc.value.reason == reason
    assert exc.value.code == "PLANNER_ERROR" and exc.value.status == 502


# ----------------------------------------------------------------------------- vLLM client
def _model() -> PlannerModel:
    return PlannerModel(
        key="planner", model_id="Qwen/Qwen3.5-9B", base_url="http://models:8040/v1",
        max_output_tokens=160, timeout_s=5.0, prompt="coach.v1",
    )  # fmt: skip


def _client(handler) -> VllmClient:
    return VllmClient(_model(), transport=httpx.MockTransport(handler))


def test_vllm_client_success_json_mode() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(GOOD)}}]})

    client = _client(handler)
    out = client.complete(MESSAGES)
    client.close()
    assert isinstance(out, PlannerOutput) and out.confidence == 0.9
    assert seen["url"] == "http://models:8040/v1/chat/completions"
    assert seen["body"]["model"] == "Qwen/Qwen3.5-9B"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["max_tokens"] == 160 and seen["body"]["messages"] == MESSAGES


def test_vllm_client_http_status_error() -> None:
    client = _client(lambda request: httpx.Response(503, text="busy"))
    with pytest.raises(PlannerError) as exc:
        client.complete(MESSAGES)
    assert exc.value.reason == "http_status" and exc.value.details["status"] == 503


def test_vllm_client_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(PlannerError) as exc:
        _client(handler).complete(MESSAGES)
    assert exc.value.reason == "http_error" and exc.value.details["kind"] == "ReadTimeout"


def test_vllm_client_bad_shape_and_invalid_json() -> None:
    with pytest.raises(PlannerError) as exc:
        _client(lambda r: httpx.Response(200, json={"choices": []})).complete(MESSAGES)
    assert exc.value.reason == "bad_response_shape"
    with pytest.raises(PlannerError) as exc:
        _client(
            lambda r: httpx.Response(200, json={"choices": [{"message": {"content": 5}}]})
        ).complete(MESSAGES)
    assert exc.value.reason == "bad_response_shape"
    with pytest.raises(PlannerError) as exc:
        _client(lambda r: httpx.Response(200, text="not json")).complete(MESSAGES)
    assert exc.value.reason == "invalid_json"


def test_vllm_client_default_model_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTCV_PLANNER_MODEL", "planner_small")
    client = VllmClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert client.model.key == "planner_small" and client.model.model_id == "Qwen/Qwen3.5-2B"
    client.close()


# ----------------------------------------------------------------------------- replay
def test_cassette_key_is_order_and_whitespace_stable() -> None:
    a = cassette_key(MESSAGES)
    b = cassette_key([{"content": "s", "role": "system"}, {"content": "u", "role": "user"}])
    assert a == b and len(a) == 64
    assert cassette_key([*MESSAGES, {"role": "user", "content": "x"}]) != a


def test_replay_client_loads_three_cassettes() -> None:
    client = ReplayClient()
    assert client.cassette_dir == default_cassette_dir()
    assert client.names == ["intent_confirmation", "refusal", "step"]


def test_replay_client_missing_raises_clear_error(tmp_path: Path) -> None:
    client = ReplayClient(tmp_path)
    with pytest.raises(CassetteMissingError) as exc:
        client.complete(MESSAGES)
    details = exc.value.details
    assert details["sha256"] == cassette_key(MESSAGES)
    assert details["cassette_dir"] == str(tmp_path) and details["available"] == []
    assert "make_cassettes.py" in details["hint"]
    assert isinstance(exc.value, PlannerError)


def test_replay_client_add_and_write(tmp_path: Path) -> None:
    out = PlannerOutput.model_validate(GOOD)
    write_cassette(tmp_path / "x.json", "x", MESSAGES, out)
    client = ReplayClient(tmp_path)
    assert client.names == ["x"]
    replayed = client.complete(MESSAGES)
    assert replayed == out and replayed is not out
    key = client.add([{"role": "user", "content": "other"}], out, name="inline")
    assert key == cassette_key([{"role": "user", "content": "other"}])
    assert client.complete([{"role": "user", "content": "other"}]) == out


def test_replay_client_detects_stale_hash(tmp_path: Path) -> None:
    payload = {"name": "stale", "sha256": "0" * 64, "messages": MESSAGES, "response": GOOD}
    (tmp_path / "stale.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PlannerError) as exc:
        ReplayClient(tmp_path)
    assert exc.value.reason == "cassette_stale"
