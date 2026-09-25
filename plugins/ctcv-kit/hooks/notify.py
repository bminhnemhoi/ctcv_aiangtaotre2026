"""PostToolUseFailure hook for Bash (brief §11): record failed commands.

Appends ``{ts, session_id, tool_name, command, error}`` (secrets masked, truncated) to
``docs/status/errors.log`` so the orchestrator can aggregate failures. Never blocks.
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
    short,
    utf8_streams,
)

ERRORS_LOG = Path("docs") / "status" / "errors.log"
COMMAND_CHARS = 300
ERROR_CHARS = 500
ERROR_KEYS = ("error", "tool_response", "tool_result", "message")


def error_text(data: dict) -> str:
    """Best-effort extraction of the failure description from the payload."""
    for key in ERROR_KEYS:
        value = data.get(key)
        if isinstance(value, dict):
            value = value.get("error") or value.get("message") or value
        if value:
            return str(value)
    return ""


def main() -> int:
    """Hook entry point; fails open."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        eprint(f"notify: dữ liệu hook không đọc được ({error}) — bỏ qua")
        return 0
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    command, _ = mask_secrets(str(tool_input.get("command") or ""))
    message, _ = mask_secrets(error_text(data))
    record = {
        "ts": now_iso(),
        "session_id": str(data.get("session_id") or ""),
        "tool_name": str(data.get("tool_name") or ""),
        "command": short(command, COMMAND_CHARS),
        "error": short(message, ERROR_CHARS),
    }
    try:
        append_jsonl(project_dir(data) / ERRORS_LOG, record)
    except OSError as exc:
        eprint(f"notify: không ghi được errors.log ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
