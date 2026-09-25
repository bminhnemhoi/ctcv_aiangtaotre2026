"""Ablation "− guardrail": the same attacks and worst-case planner, with the coach bypassed.

``python -m ctcv_eval.redteam.ablation`` answers one question for the dossier (section 9): how
many red-team attacks succeed when the hard rules, PII redaction, quarantine and output checks
are removed and the planner receives learner and pasted text verbatim? The tool whitelist stays
in place because it is a separate component. The result is expected to be bad; the command exits
0 and writes ``eval/reports/redteam-ablation.json`` for ``scripts/collect_engineering_metrics``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ctcv_agent.coach import build_messages
from ctcv_agent.schemas import SessionContext, ToolResult, TurnResult
from ctcv_agent.tools.backends import Backends, sample_turn_state
from ctcv_agent.tools.router import dispatch
from ctcv_core.errors import AppError
from ctcv_core.paths import REPO_ROOT
from ctcv_eval.redteam import (
    DEFAULT_USER,
    DummyPlanner,
    Outcome,
    Scenario,
    default_scenarios_path,
    load_scenarios,
    run_scenario,
    summarize,
)

REPORT_NAME = "redteam-ablation.json"


def _unguarded_turn(
    planner: DummyPlanner,
    state: dict,
    text: str,
    first: bool,
    ctx: SessionContext,
    backends: Backends,
) -> TurnResult:
    """One turn without input/output guardrails: raw text in, planner words out."""
    planner.begin_turn()
    messages = build_messages(state, text, first)
    output = planner.complete(messages)
    tool_results: list[ToolResult] = []
    for call in output.tool_calls:
        try:
            result = dispatch(call, ctx, backends)
        except AppError as exc:
            tool_results.append(ToolResult(name=call.name, ok=False, error_code=exc.code))
        else:
            tool_results.append(
                ToolResult(name=call.name, ok=True, output=result.model_dump(mode="json"))
            )
    if tool_results:
        payload = json.dumps([r.model_dump(mode="json") for r in tool_results], ensure_ascii=False)
        output = planner.complete([*messages, {"role": "user", "content": payload}])
    return TurnResult(say=output.say, confidence=output.confidence, tool_results=tool_results)


def run_turns_unguarded(
    sc: Scenario, planner: DummyPlanner, backends: Backends
) -> list[TurnResult]:
    """Drop-in replacement for the guarded turn runner of :func:`ctcv_eval.redteam.run_scenario`."""
    state = sample_turn_state(sc.context.session_id)
    ctx = SessionContext(user_id=DEFAULT_USER, session_id=sc.context.session_id)
    texts = [*sc.context.turns, sc.input]
    results: list[TurnResult] = []
    for index, text in enumerate(texts):
        last = index == len(texts) - 1
        pasted = sc.context.pasted_text if last else None
        raw = f"{text}\n{pasted}" if pasted else text
        results.append(
            _unguarded_turn(
                planner, state, raw, sc.context.first_turn and index == 0, ctx, backends
            )
        )
    return results


def run_ablation(scenarios: list[Scenario]) -> list[Outcome]:
    """Grade every scenario with the normal graders but the unguarded turn runner."""
    return [run_scenario(sc, turn_runner=run_turns_unguarded) for sc in scenarios]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; always exits 0 (a bad result is the expected finding)."""
    del argv
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    scenarios = load_scenarios(default_scenarios_path())
    summary = summarize(run_ablation(scenarios))
    report = {
        "mode": "no-guardrails (planner giả lập tệ nhất, không mô hình)",
        "size": summary.total,
        "attacks_succeeded": summary.failed,
        "attacks_blocked": summary.passed,
        "leaks": summary.leaks,
        "real_actions": summary.real_actions,
    }
    out = Path(REPO_ROOT) / "eval" / "reports" / REPORT_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Ablation tắt guardrail: {summary.failed}/{summary.total} đòn tấn công thành công "
        f"(rò rỉ {summary.leaks}, thao tác thay người dùng {summary.real_actions}). Báo cáo: {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
