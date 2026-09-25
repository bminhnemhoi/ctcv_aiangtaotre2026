"""Regenerate the replay cassettes in services/agent/tests/cassettes/.

Run: ``uv run python services/agent/tests/make_cassettes.py``. Cassettes are keyed by the
SHA-256 of the exact planner messages, so re-run this after changing
``config/prompts/coach.v1.md`` or the sample state in ``ctcv_agent.tools.backends``.
"""

from __future__ import annotations

from pathlib import Path

from ctcv_agent.coach import build_messages
from ctcv_agent.planner import write_cassette
from ctcv_agent.schemas import ActionHint, PlannerOutput, ToolCall
from ctcv_agent.tools.backends import sample_turn_state

CASSETTE_DIR = Path(__file__).resolve().parent / "cassettes"
HINT = ActionHint(element_id="btn_qr", color="xanh", label="Quét QR")

# name → (user_text, first_turn, planner reply)
CASES: dict[str, tuple[str, bool, PlannerOutput]] = {
    "intent_confirmation": (
        "Cháu ơi, bác muốn chuyển tiền cho con",
        True,
        PlannerOutput(say="Bác muốn chuyển tiền cho con hay trả tiền hàng ạ?", confidence=0.95),
    ),
    "step": (
        "Chuyển cho con.",
        False,
        PlannerOutput(
            say="Vậy mình chuyển cho con nhé. Bác bấm nút xanh có chữ Quét QR ở giữa màn hình nhé.",
            action_hint=HINT,
            confidence=0.9,
        ),
    ),
    "refusal": (
        "Bác quên mất rồi, cháu đọc mã giúp bác với",
        False,
        PlannerOutput(
            say=(
                "Bác đừng đọc mã này cho ai, kể cả cháu nhé. "
                "Mình tập tiếp trên ứng dụng mô phỏng, bác bấm nút xanh có chữ Quét QR nhé."
            ),
            action_hint=HINT,
            tool_calls=[
                ToolCall(name="escalate_to_volunteer", args={"reason": "nguoi hoc nho doc ma"})
            ],
            confidence=0.8,
        ),
    ),
}


def main() -> None:
    """Write one cassette per case."""
    CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    state = sample_turn_state("sess-demo-1")
    for name, (user_text, first_turn, reply) in CASES.items():
        messages = build_messages(state, user_text, first_turn)
        write_cassette(CASSETTE_DIR / f"{name}.json", name, messages, reply)
        print(f"wrote {name}.json")


if __name__ == "__main__":
    main()
