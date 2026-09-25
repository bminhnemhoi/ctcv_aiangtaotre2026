"""UserPromptSubmit hook (brief §11): block prompts that carry secrets, log the rest.

Blocks (exit 2, Vietnamese reason) when the prompt contains secret-looking tokens —
``sk-…``, ``ghp_…``, ``hf_…``, ``AKIA…``, ``password=<value>``, a ≥ 40-character
base64-like string after key/secret/token, private-key headers, JWTs. Every prompt
(masked) is appended to ``docs/status/prompts.log`` (gitignored). Fails open on
malformed input.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _common import (
    append_jsonl,
    block,
    eprint,
    mask_secrets,
    now_iso,
    project_dir,
    read_stdin_json,
    utf8_streams,
)

PROMPTS_LOG = Path("docs") / "status" / "prompts.log"


def main() -> int:
    """Hook entry point."""
    utf8_streams()
    data, error = read_stdin_json()
    if data is None:
        eprint(f"prompt-guard: dữ liệu hook không đọc được ({error}) — bỏ qua")
        return 0
    prompt = data.get("prompt")
    if not isinstance(prompt, str):
        prompt = data.get("user_input") if isinstance(data.get("user_input"), str) else ""
    masked, kinds = mask_secrets(prompt)
    record = {
        "ts": now_iso(),
        "session_id": str(data.get("session_id") or ""),
        "blocked": bool(kinds),
        "kinds": kinds,
        "prompt": masked,
    }
    try:
        append_jsonl(project_dir(data) / PROMPTS_LOG, record)
    except OSError as exc:
        eprint(f"prompt-guard: không ghi được prompts.log ({exc})")
    if kinds:
        block(
            "prompt chứa chuỗi giống bí mật ("
            + ", ".join(kinds)
            + "). Xóa/che giá trị rồi gửi lại; "
            "bí mật chỉ đặt trong .env (không commit) hoặc GitHub Secrets."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
