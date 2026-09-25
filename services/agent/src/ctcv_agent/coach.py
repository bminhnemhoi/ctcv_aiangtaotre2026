"""One coaching turn: input guardrails → planner → tool loop → output guardrails.

This is the only module that both talks to the planner and dispatches tools. Pasted or
third-party text is summarised by the quarantine into a closed schema before anything
reaches the planner; the raw text never appears in a planner message (SEC-03, D28).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ctcv_agent.guardrails import (
    enforce_style,
    looks_like_pasted_content,
    redact_pii,
    refuses_real_action,
    refuses_sensitive_request,
    requires_citation,
    rules,
)
from ctcv_agent.planner import (
    Message,
    PlannerClient,
    PlannerError,
    load_system_prompt,
    planner_model,
)
from ctcv_agent.quarantine import QuarantineSummarizer, QuarantineSummary, RuleBasedQuarantine
from ctcv_agent.schemas import (
    ActionHint,
    Citation,
    PlannerOutput,
    SessionContext,
    ToolCall,
    ToolResult,
    TurnResult,
)
from ctcv_agent.tools.router import dispatch
from ctcv_core.errors import AppError

MAX_TOOL_CALLS = 3
ESCALATE_TOOL = "escalate_to_volunteer"
VERIFY_TOOL = "verify_citation"
TERMINAL_TOOLS: frozenset[str] = frozenset({ESCALATE_TOOL, "log_progress"})
ANONYMOUS_USER = "anonymous"

# Fixed Vietnamese lines (vetted by tests against enforce_style and banned terms).
REFUSAL_SENSITIVE = (
    "Bác đừng đọc mã này cho ai, kể cả cháu nhé. "
    "Mình chỉ tập trên ứng dụng mô phỏng, không cần mã thật đâu ạ."
)
REFUSAL_REAL_ACTION = (
    "Cháu chỉ tập cùng bác trên ứng dụng mô phỏng thôi, bác tự bấm để quen tay nhé."
)
SAFE_FALLBACK = "Cháu chưa chắc bước này, để cháu mời tình nguyện viên giúp bác nhé."
NO_SOURCE = "Cháu chưa chắc phần này, để cháu mời tình nguyện viên giúp bác nhé."
INTENT_FALLBACK = "Bác muốn tập bài này để làm gì ạ?"

ToolRouter = Callable[[ToolCall, SessionContext], BaseModel]
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass
class _Plan:
    """Mutable scratch state of the planner/tool loop."""

    out: PlannerOutput | None = None
    results: list[ToolResult] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    calls_made: int = 0
    escalate: bool = False
    escalated_via_tool: bool = False


# ----------------------------------------------------------------------------- helpers
def _state_dict(state: Mapping[str, Any] | BaseModel | None) -> dict[str, Any]:
    if state is None:
        return {}
    if isinstance(state, BaseModel):
        return state.model_dump(mode="json")
    return dict(state)


def _state_numbers(value: Any) -> set[str]:
    """Numbers written in the state, kept whole (``200.000``): repeating one needs no citation."""
    found: set[str] = set()
    if isinstance(value, Mapping):
        for item in value.values():
            found |= _state_numbers(item)
    elif isinstance(value, list | tuple):
        for item in value:
            found |= _state_numbers(item)
    elif isinstance(value, bool):
        return found
    elif isinstance(value, int | float | str):
        found |= set(_NUMBER_RE.findall(str(value)))
    return found


def build_messages(
    state: Mapping[str, Any] | BaseModel | None,
    user_text: str,
    first_turn: bool,
    *,
    pasted_summary: QuarantineSummary | None = None,
    system_prompt: str | None = None,
) -> list[Message]:
    """Deterministic planner messages: system prompt + one JSON user payload.

    ``user_text`` must already be PII-redacted and must be the learner's own words;
    pasted content only enters as ``pasted_summary`` (closed schema).
    """
    payload = {
        "first_turn": first_turn,
        "state": _state_dict(state),
        "user_text": user_text,
        "pasted_summary": pasted_summary.model_dump(mode="json") if pasted_summary else None,
    }
    system = (
        system_prompt if system_prompt is not None else load_system_prompt(planner_model().prompt)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def _tool_results_message(results: Iterable[ToolResult], budget_left: int) -> Message:
    """Tool results for the planner; ``budget_left == 0`` tells it to answer without tools."""
    content = {
        "kind": "tool_results",
        "results": [r.model_dump(mode="json") for r in results],
        "budget_left": budget_left,
    }
    return {"role": "user", "content": json.dumps(content, ensure_ascii=False, sort_keys=True)}


def _citation_from(output: BaseModel) -> Citation | None:
    data = output.model_dump(mode="json")
    if not data.get("supported"):
        return None
    return Citation(
        doc_id=data["doc_id"],
        url=data["url"],
        title=data["title"],
        effective_date=data.get("effective_date"),
        quote=data.get("quote", ""),
    )


def _dispatch_one(
    router: ToolRouter, call: ToolCall, ctx: SessionContext, plan: _Plan
) -> ToolResult:
    """Dispatch one call; tool/whitelist errors become structured results, never crashes."""
    try:
        output = router(call, ctx)
    except AppError as exc:
        plan.reasons.append(f"tool_error:{call.name}:{exc.code}")
        result = ToolResult(name=call.name, ok=False, error_code=exc.code)
    else:
        result = ToolResult(name=call.name, ok=True, output=output.model_dump(mode="json"))
        if call.name == ESCALATE_TOOL:
            plan.escalate = plan.escalated_via_tool = True
        elif call.name == VERIFY_TOOL:
            citation = _citation_from(output)
            if citation is not None:
                plan.citations.append(citation)
    plan.results.append(result)
    return result


def _plan(
    messages: list[Message],
    planner: PlannerClient,
    router: ToolRouter,
    ctx: SessionContext,
    budget: int,
) -> _Plan:
    """Call the planner, dispatch its tool calls (at most ``budget`` per turn) and loop.

    When the planner keeps asking for tools after the budget is spent it is re-prompted with
    ``budget_left: 0`` so it can answer from what it already has; the loop itself is bounded.
    """
    plan = _Plan()
    for _ in range(budget + 1):
        try:
            out = planner.complete(messages)
        except PlannerError as exc:
            plan.reasons.append(f"planner_error:{exc.reason}")
            plan.out = None
            return plan
        plan.out = out
        if not out.tool_calls:
            return plan
        remaining = budget - plan.calls_made
        calls = out.tool_calls[:remaining]
        if len(out.tool_calls) > remaining and "tool_budget_exceeded" not in plan.reasons:
            plan.reasons.append("tool_budget_exceeded")
        results = [_dispatch_one(router, call, ctx, plan) for call in calls]
        plan.calls_made += len(calls)
        if plan.escalated_via_tool or (calls and all(c.name in TERMINAL_TOOLS for c in calls)):
            return plan
        messages = [
            *messages,
            {"role": "assistant", "content": out.model_dump_json()},
            _tool_results_message(results, budget - plan.calls_made),
        ]
    return plan


def _hint_from_state(state: Mapping[str, Any]) -> ActionHint | None:
    nxt = state.get("next_action")
    if not isinstance(nxt, Mapping) or not nxt.get("element_id"):
        return None
    try:
        return ActionHint(
            element_id=nxt["element_id"], color=nxt.get("color") or "", label=nxt.get("label") or ""
        )
    except ValueError:
        return None


def _fallback_say(
    state: Mapping[str, Any], first_turn: bool
) -> tuple[str, ActionHint | None, bool]:
    """A safe line when the planner's line failed the style check: ``(say, hint, escalate)``."""
    if first_turn:
        question = str(state.get("intent_confirmation") or "")
        if question and enforce_style(question, True, has_action=False).ok:
            return question, None, False
        return INTENT_FALLBACK, None, False
    line = str(state.get("coach_line") or "")
    hint = _hint_from_state(state)
    if line and enforce_style(line, False, has_action=True, hint=hint).ok:
        return line, hint, False
    return SAFE_FALLBACK, None, True


def _finalize(plan: _Plan, state: Mapping[str, Any], first_turn: bool) -> TurnResult:
    """Output guardrails: redaction, confidence, style, citation requirement."""
    out = plan.out
    if out is None:
        return TurnResult(
            say=SAFE_FALLBACK,
            escalate=True,
            reasons=[*plan.reasons, "planner_unavailable"],
            tool_results=plan.results,
        )
    say, hint, escalate, reasons = (
        redact_pii(out.say).strip(),
        out.action_hint,
        plan.escalate,
        list(plan.reasons),
    )
    if out.confidence < rules().escalate_confidence:
        escalate = True
        reasons.append("low_confidence")
    expects_action = hint is not None or (not first_turn and not escalate)
    verdict = enforce_style(say, first_turn, has_action=expects_action, hint=hint)
    if not verdict.ok:
        reasons.append("style:" + "; ".join(verdict.reasons))
        say, hint, must_escalate = _fallback_say(state, first_turn)
        escalate = escalate or must_escalate
    if requires_citation(say, plan.citations, known_values=_state_numbers(state)):
        reasons.append("fact_without_citation")
        say, hint, escalate = NO_SOURCE, None, True
    return TurnResult(
        say=say,
        action_hint=hint,
        escalate=escalate,
        reasons=reasons,
        citations=list(plan.citations),
        confidence=out.confidence,
        tool_results=plan.results,
    )


def _escalate(
    router: ToolRouter, ctx: SessionContext, reason: str, result: TurnResult
) -> TurnResult:
    """Flag the session through the whitelisted tool; failures are recorded, not raised."""
    call = ToolCall(name=ESCALATE_TOOL, args={"reason": reason[:200]})
    try:
        output = router(call, ctx)
    except AppError as exc:
        result.reasons.append(f"tool_error:{ESCALATE_TOOL}:{exc.code}")
        return result
    result.tool_results.append(
        ToolResult(name=ESCALATE_TOOL, ok=True, output=output.model_dump(mode="json"))
    )
    return result


def _refusal(kind: str, say: str, router: ToolRouter, ctx: SessionContext) -> TurnResult:
    result = TurnResult(say=say, escalate=True, refused=True, reasons=[kind], confidence=1.0)
    return _escalate(router, ctx, kind, result)


# ----------------------------------------------------------------------------- entry point
def run_turn(
    state: Mapping[str, Any] | BaseModel | None,
    user_text: str,
    first_turn: bool,
    planner: PlannerClient,
    tools_router: ToolRouter = dispatch,
    *,
    ctx: SessionContext | None = None,
    pasted_text: str | None = None,
    quarantine: QuarantineSummarizer | None = None,
    max_tool_calls: int = MAX_TOOL_CALLS,
) -> TurnResult:
    """Run one coaching turn and return what to say, highlight and whether to escalate.

    Args:
        state: Structured sandbox state from the engine (never raw learner input).
        user_text: What the learner said or typed (PII is redacted here).
        first_turn: True for the first turn of a scenario (intent must be confirmed).
        planner: The planner client (vLLM in production, ReplayClient/stubs in tests).
        tools_router: ``(ToolCall, SessionContext) -> Output``; defaults to the whitelist router.
        ctx: Trusted session context from the JWT; anonymous when omitted.
        pasted_text: Third-party content the learner pasted, if the UI knows it; when
            omitted, ``user_text`` is quarantined whenever it looks pasted.
        quarantine: Summariser for untrusted text (rule-based by default).
        max_tool_calls: Budget of tool calls for this turn.
    """
    state_map = _state_dict(state)
    context = ctx or SessionContext(user_id=ANONYMOUS_USER, session_id=state_map.get("session_id"))
    raw = user_text or ""
    if pasted_text is None and looks_like_pasted_content(raw):
        pasted_text, raw = raw, ""
    spoken = redact_pii(raw)
    if refuses_sensitive_request(spoken):
        return _refusal("sensitive_request", REFUSAL_SENSITIVE, tools_router, context)
    if refuses_real_action(spoken):
        return _refusal("real_action_request", REFUSAL_REAL_ACTION, tools_router, context)
    summary = (quarantine or RuleBasedQuarantine()).summarize(pasted_text) if pasted_text else None
    messages = build_messages(state_map, spoken, first_turn, pasted_summary=summary)
    plan = _plan(messages, planner, tools_router, context, max_tool_calls)
    result = _finalize(plan, state_map, first_turn)
    if summary is not None:
        result.reasons.append("pasted_content_quarantined")
    if result.escalate and not plan.escalated_via_tool:
        result = _escalate(tools_router, context, ",".join(result.reasons) or "escalate", result)
    return result
