"""SubagentStop hook (brief §11, D20): log the subagent summary and keep its transcript.

Appends ``{ts, session_id, agent_id, agent_type, summary}`` (summary = first 200
characters of the last assistant message, secrets masked) to
``docs/status/subagents.log`` and copies ``agent_transcript_path`` (or a
``transcript_path`` that belongs to the subagent) to
``docs/prompt-log/subagents/<session_id>-<agent_id>.jsonl``. Never blocks.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _common import (
    append_jsonl,
    eprint,
    mask_secrets,
    now_iso,
    project_dir,
    read_stdin_json,
    safe_id,
    utf8_streams,
)
from promptlog import PROMPT_LOG, SUBAGENTS, copy_transcript

SUBAGENT_LOG = Path("docs") / "status" / "subagents.log"
SUMMARY_CHARS = 200


def agent_transcript(data: dict, session_id: str) -> Path | None:
    """Locate the subagent transcript in the payload (fallback: a non-session transcript)."""
    raw = data.get("agent_transcript_path")
    if not isinstance(raw, str) or not raw:
        raw = data.get("transcript_path")
        if not isinstance(raw, str) or not raw or Path(raw).stem == session_id:
            return None
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def main() -> int:
    """Hook entry point; fails open."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        eprint(f"subagent-log: dữ liệu hook không đọc được ({error}) — bỏ qua")
        return 0
    root = project_dir(data)
    session_id = safe_id(data.get("session_id"))
    agent_id = safe_id(data.get("agent_id"), "agent")
    summary, _ = mask_secrets(" ".join(str(data.get("last_assistant_message") or "").split()))
    record = {
        "ts": now_iso(),
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": str(data.get("agent_type") or "unknown"),
        "summary": summary[:SUMMARY_CHARS],
    }
    try:
        append_jsonl(root / SUBAGENT_LOG, record)
        src = agent_transcript(data, session_id)
        if src is not None:
            copy_transcript(src, root / PROMPT_LOG / SUBAGENTS / f"{session_id}-{agent_id}.jsonl")
    except OSError as exc:
        eprint(f"subagent-log: không ghi được ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
