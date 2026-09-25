#!/usr/bin/env bash
# Shared helpers for deploy/scripts/*.sh (plan §8). Source it; never run it.
#   source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# Provides: logging, --dry-run aware `run`, safe .env loading, ssh/compose wrappers,
# Telegram notification, timers. Secrets are never echoed (SEC-01): commands that carry a
# token are described, not printed.
set -euo pipefail

# ----------------------------------------------------------------------------- paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_DIR_LOCAL="${REPO_ROOT}/deploy"
COMPOSE_BASE="deploy/docker-compose.yml"
COMPOSE_PROD="deploy/docker-compose.prod.yml"

DRY_RUN="${DRY_RUN:-0}"
CTCV_ENV_FILE="${CTCV_ENV_FILE:-${REPO_ROOT}/.env}"

# ----------------------------------------------------------------------------- output
log()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
warn() { printf '[%s] CẢNH BÁO: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die()  { printf '[%s] LỖI: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit "${2:-1}"; }

# run <cmd...>: execute, or print with a [dry-run] prefix when DRY_RUN=1.
run() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

# run_sh "<shell string>": like run but for pipelines / redirections.
run_sh() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] %s\n' "$1"
    return 0
  fi
  bash -eo pipefail -c "$1"
}

# ----------------------------------------------------------------------------- env
# Load KEY=VALUE lines from the repo-root .env without executing it (no `source`).
load_env_file() {
  local file="${1:-${CTCV_ENV_FILE}}" key value
  [[ -f "${file}" ]] || { log "Không có file env ${file##*/} — dùng biến môi trường hiện có"; return 0; }
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${line}" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"
    value="${value%\"}"; value="${value#\"}"; value="${value%\'}"; value="${value#\'}"
    # Existing environment wins (CI secrets / make VAR=... override the file).
    if [[ -z "${!key+x}" ]]; then export "${key}=${value}"; fi
  done < "${file}"
  log "Đã nạp biến từ ${file##*/} (không in giá trị)"
}

# require_env VAR...: fail with a Vietnamese message listing every missing variable.
require_env() {
  local missing=() name
  for name in "$@"; do
    [[ -n "${!name:-}" && "${!name:-}" != "CHANGE_ME" ]] || missing+=("${name}")
  done
  if ((${#missing[@]})); then
    die "Thiếu biến môi trường: ${missing[*]} (điền vào .env, xem deploy/README.md)" 2
  fi
}

# env_or VAR default
env_or() { printf '%s' "${!1:-$2}"; }

# ----------------------------------------------------------------------------- remote
# Target host for an environment: DEPLOY_HOST_STAGING / DEPLOY_HOST_PROD override DEPLOY_HOST.
resolve_deploy_host() {
  local env_name="$1" upper
  upper="$(printf '%s' "${env_name}" | tr '[:lower:]' '[:upper:]')"
  local specific="DEPLOY_HOST_${upper}"
  printf '%s' "${!specific:-${DEPLOY_HOST:-}}"
}

ssh_opts() {
  local opts=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
  [[ -n "${SSH_KEY_FILE:-}" ]] && opts+=(-i "${SSH_KEY_FILE}")
  [[ -n "${DEPLOY_SSH_PORT:-}" ]] && opts+=(-p "${DEPLOY_SSH_PORT}")
  printf '%s\n' "${opts[@]}"
}

# ssh_run <host> "<command>": run a command on the deploy host (user from DEPLOY_USER).
ssh_run() {
  local host="$1" cmd="$2" opts=()
  mapfile -t opts < <(ssh_opts)
  run ssh "${opts[@]}" "${DEPLOY_USER:-deploy}@${host}" "${cmd}"
}

# rsync_deploy_dir <host>: copy deploy/ (compose, caddy, monitoring) to DEPLOY_DIR on the host.
rsync_deploy_dir() {
  local host="$1" rsh="ssh" opts=()
  mapfile -t opts < <(ssh_opts)
  rsh="ssh ${opts[*]}"
  run rsync -az --delete \
    --exclude 'backups/' --exclude 'models/cache/' --exclude 'tests/' \
    -e "${rsh}" "${DEPLOY_DIR_LOCAL}/" "${DEPLOY_USER:-deploy}@${host}:${DEPLOY_DIR:-/opt/ctcv}/deploy/"
}

# remote_env_upsert KEY VALUE: shell snippet (run on the host) that sets KEY=VALUE in ./.env,
# replacing an existing line or appending one. VALUE must not contain '#' or quotes.
remote_env_upsert() {
  printf "{ grep -q '^%s=' .env && sed -i 's#^%s=.*#%s=%s#' .env || printf '%s=%s\\\\n' >> .env; }" \
    "$1" "$1" "$1" "$2" "$1" "$2"
}

# compose_cmd <profile>: the compose invocation used on the host (root .env drives interpolation).
compose_cmd() {
  printf 'docker compose --env-file .env -f %s -f %s --profile %s' "${COMPOSE_BASE}" "${COMPOSE_PROD}" "$1"
}

# ----------------------------------------------------------------------------- telegram
# notify_telegram "<text>": plan §8 alert channel. Token never appears in output.
notify_telegram() {
  local text="$1"
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] telegram notify: %s\n' "${text}"
    return 0
  fi
  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" \
        || "${TELEGRAM_BOT_TOKEN}" == "CHANGE_ME" ]]; then
    warn "Chưa cấu hình TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID — bỏ qua thông báo: ${text}"
    return 0
  fi
  if curl -fsS --max-time 15 -o /dev/null \
      -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=${text}" \
      --data-urlencode "disable_web_page_preview=true"; then
    log "Đã gửi Telegram"
  else
    warn "Gửi Telegram thất bại (không dừng quy trình)"
  fi
}

# ----------------------------------------------------------------------------- misc
timer_start() { TIMER_T0="$(date +%s)"; }
timer_elapsed() { printf '%s' "$(( $(date +%s) - ${TIMER_T0:-$(date +%s)} ))"; }

git_default_tag() {
  (cd "${REPO_ROOT}" && git describe --tags --always 2>/dev/null) || printf 'dev'
}

# newest_file <dir> <glob>: newest matching regular file by mtime (empty when none).
newest_file() {
  local dir="$1" pattern="$2"
  [[ -d "${dir}" ]] || return 0
  find "${dir}" -maxdepth 1 -type f -name "${pattern}" -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -n1 | cut -d' ' -f2-
}

# scenario_ids: ids of shipped sandbox scenarios (file names), one per line.
scenario_ids() {
  local f
  for f in "${REPO_ROOT}"/sandbox/scenarios/*.json; do
    [[ -e "${f}" ]] || continue
    f="${f##*/}"; printf '%s\n' "${f%.json}"
  done
}

usage_common() {
  cat <<'USAGE'
Cờ chung:
  --dry-run       Chỉ in các lệnh sẽ chạy (dùng trong test), không đụng máy chủ
  -h, --help      Hướng dẫn
USAGE
}
