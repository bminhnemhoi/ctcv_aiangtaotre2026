"""Print a Vietnamese Makefile message by key (``python scripts/msg.py <key> [args...]``).

Why: GNU make from winget (ezwinports) hands recipe lines to bash through the ANSI code
page, so any non-ASCII text inside a recipe arrives garbled on Windows. Keeping recipes
ASCII-only and routing messages through Python (which writes UTF-8 itself) makes
``make`` output identical on Windows Git Bash and Linux CI.
"""

from __future__ import annotations

import sys

MESSAGES: dict[str, str] = {
    "not-implemented": "CHƯA HIỆN THỰC — xem epics/{0}.md",
    "compose-missing": "  (deploy/docker-compose.yml do WP I tạo)",
    "skip-e2e": (
        "BỎ QUA e2e: đặt E2E=1 để chạy Playwright (cần pnpm install và playwright install chromium)"
    ),
    "e2e-no-web": "E2E=1 nhưng chưa có apps/web — bỏ qua playwright install",
    "no-integration-tests": "integration: chưa có test tích hợp (testcontainers từ E02) — OK",
    "gitleaks-missing": (
        "CẢNH BÁO: thiếu gitleaks — bỏ qua quét secret (Windows: winget install Gitleaks.Gitleaks)"
    ),
    "gitleaks-clean": "gitleaks: sạch",
    "check-green": "make check: XANH (QUICK={0})",
    "precommit-installed": "pre-commit: đã cài hook vào .git/hooks",
    "need-tag": "Cần TAG=vX.Y (ví dụ: make rollback TAG=v0.1)",
    "a11y-missing": "a11y: CHƯA HIỆN THỰC — xem epics/E11.md",
}


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def render(key: str, args: list[str]) -> str:
    """Return the formatted message for ``key``; unknown keys raise ``KeyError``."""
    return MESSAGES[key].format(*args)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _utf8_stdout()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Cách dùng: python scripts/msg.py <key> [tham số...]", file=sys.stderr)
        return 2
    try:
        print(render(args[0], args[1:]))
    except (KeyError, IndexError):
        print(f"msg.py: không có thông điệp '{args[0]}' hoặc thiếu tham số", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
