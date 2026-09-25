"""Router: unknown tools, bad args, side effects, config agreement."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from ctcv_agent import router as public_router
from ctcv_agent.schemas import SessionContext, ToolCall
from ctcv_agent.tools import TOOL_REGISTRY as LAZY_REGISTRY
from ctcv_agent.tools.backends import Backends
from ctcv_agent.tools.base import ToolSpec
from ctcv_agent.tools.registry import TOOL_REGISTRY, tool_names
from ctcv_agent.tools.router import ToolNotAllowed, allowed_tools, dispatch, resolve, validate_args
from ctcv_core.config import load_config


def test_registry_is_read_only_and_lazy_alias_is_same_object() -> None:
    assert isinstance(TOOL_REGISTRY, MappingProxyType)
    assert LAZY_REGISTRY is TOOL_REGISTRY
    with pytest.raises(TypeError):
        TOOL_REGISTRY["send_money"] = None  # type: ignore[index]
    assert tool_names() == set(allowed_tools())


def test_public_alias_exports_router() -> None:
    assert public_router.dispatch is dispatch
    assert public_router.ToolNotAllowed is ToolNotAllowed


@pytest.mark.parametrize(
    "name", ["send_money", "transfer", "sms", "payment", "os_system", "get_session_state2"]
)
def test_unknown_tool_refused(name: str, ctx: SessionContext, backends: Backends) -> None:
    with pytest.raises(ToolNotAllowed) as exc:
        dispatch(ToolCall(name=name, args={}), ctx, backends)
    assert exc.value.code == "TOOL_NOT_ALLOWED"
    assert exc.value.status == 403
    assert exc.value.details["reason"] == "unknown_tool"
    assert "tình nguyện viên" in exc.value.message_vi


def test_bad_args_refused_without_echoing_values(ctx: SessionContext, backends: Backends) -> None:
    with pytest.raises(ToolNotAllowed) as exc:
        dispatch(
            ToolCall(name="next_step", args={"session_id": "bad id with spaces 0912345678"}),
            ctx,
            backends,
        )
    details = exc.value.details
    assert details["reason"] == "invalid_args"
    assert details["errors"][0]["loc"] == "session_id"
    assert "0912345678" not in str(details)


def test_missing_arg_refused(ctx: SessionContext, backends: Backends) -> None:
    with pytest.raises(ToolNotAllowed) as exc:
        dispatch(ToolCall(name="next_step"), ctx, backends)
    assert exc.value.details["reason"] == "invalid_args"


def test_user_id_in_args_is_refused(ctx: SessionContext, backends: Backends) -> None:
    call = ToolCall(
        name="log_progress", args={"user_id": "someone-else", "skill": "an-toan-so", "level": 1}
    )
    with pytest.raises(ToolNotAllowed) as exc:
        dispatch(call, ctx, backends)
    assert exc.value.details["reason"] == "invalid_args"
    assert backends.progress.records == []


def test_dispatch_uses_context_user_not_args(ctx: SessionContext, backends: Backends) -> None:
    out = dispatch(
        ToolCall(name="log_progress", args={"skill": "an-toan-so", "level": 2}), ctx, backends
    )
    assert out.model_dump()["recorded"] is True
    assert backends.progress.records == [("user-demo", "an-toan-so", 2)]


def test_side_effects_agree_with_config() -> None:
    cfg = {t["name"]: t["side_effect"] for t in load_config("tools")["tools"]}
    for name, spec in TOOL_REGISTRY.items():
        assert spec.side_effect == cfg[name], name
        assert spec.side_effect in {"none", "sandbox", "log"}


def test_tool_not_in_config_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ctcv_agent.tools.router.allowed_tools", lambda: {})
    with pytest.raises(ToolNotAllowed) as exc:
        resolve("next_step")
    assert exc.value.details["reason"] == "not_in_config"


def test_side_effect_mismatch_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ctcv_agent.tools.router.allowed_tools",
        lambda: {"next_step": {"name": "next_step", "side_effect": "log"}},
    )
    with pytest.raises(ToolNotAllowed) as exc:
        resolve("next_step")
    assert exc.value.details["reason"] == "side_effect_mismatch"


def test_validate_args_returns_input_model() -> None:
    spec = resolve("search_guides")
    inp = validate_args(spec, {"query": "xác nhận cư trú"})
    assert inp.model_dump()["top_k"] == 3


def test_dispatch_default_backends_persist_between_calls(ctx: SessionContext) -> None:
    started = dispatch(ToolCall(name="start_drill", args={"key": "gia-danh-cong-an-goi-dien"}), ctx)
    drill_id = started.model_dump()["drill_id"]
    graded = dispatch(
        ToolCall(name="grade_drill", args={"drill_id": drill_id, "option_id": "b"}), ctx
    )
    assert graded.model_dump()["correct"] is True


def test_toolspec_from_module_validates_shape() -> None:
    from types import ModuleType

    bad = ModuleType("bad_tool")
    with pytest.raises(TypeError, match="lacks NAME"):
        ToolSpec.from_module(bad)
    bad.NAME, bad.SIDE_EFFECT = "bad", "network"
    bad.Input = bad.Output = object
    bad.run = lambda *a: None
    with pytest.raises(TypeError, match="SIDE_EFFECT"):
        ToolSpec.from_module(bad)
    bad.SIDE_EFFECT = "none"
    with pytest.raises(TypeError, match="Pydantic"):
        ToolSpec.from_module(bad)
    bad.NAME = ""
    with pytest.raises(TypeError, match="non-empty"):
        ToolSpec.from_module(bad)
