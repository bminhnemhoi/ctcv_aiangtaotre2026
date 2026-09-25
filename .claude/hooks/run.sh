#!/usr/bin/env bash
# Dispatch a Claude Code hook to its Python implementation (brief D2).
#
#   bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run.sh" <name> [args...]
#
# Picks `python3` when it is >= 3.10, otherwise `python`; then `exec`s
# .claude/hooks/<name>.py with the hook JSON still on stdin. Hooks are stdlib-only,
# so no virtualenv is needed. Windows Git Bash and Linux behave the same.
# Safety hooks (guard, protect-paths) fail CLOSED when no usable Python exists
# (brief D22); every other hook fails open with a note on stderr.
set -u

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "run.sh: thiếu tên hook (ví dụ: run.sh guard)" >&2
  exit 0
fi
shift
SCRIPT="$HOOK_DIR/$NAME.py"
CLOSED=0
case "$NAME" in guard|protect-paths) CLOSED=1 ;; esac

if [ ! -f "$SCRIPT" ]; then
  echo "run.sh: không có hook $NAME.py — bỏ qua" >&2
  [ "$CLOSED" = "1" ] && exit 2
  exit 0
fi

pick_python() {
  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PY="$(pick_python)" || {
  echo "run.sh: không tìm thấy Python >= 3.10 trên PATH — hook $NAME không chạy được" >&2
  [ "$CLOSED" = "1" ] && { echo "Chặn (hook): guard/protect-paths không chạy được nên chặn để an toàn." >&2; exit 2; }
  exit 0
}

export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
exec "$PY" "$SCRIPT" "$@"
