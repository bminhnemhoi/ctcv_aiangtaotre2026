#!/usr/bin/env bash
# Roll the running stack back to an earlier image tag in ≤ 2 minutes (plan §8, `make rollback TAG=`).
#   bash deploy/scripts/rollback.sh <TAG> [--env staging|prod] [--profile gpu|cpu]
#        [--db-downgrade <alembic-rev>] [--dry-run]
# Images are pulled by tag (no rebuild); the DB schema is left alone unless --db-downgrade
# is given (migrations are written forward-compatible — RUNBOOK §3).
set -euo pipefail
# shellcheck source=deploy/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  cat <<'USAGE'
Cách dùng: rollback.sh <TAG> [--env staging|prod] [--profile gpu|cpu] [--db-downgrade REV] [--dry-run]
  TAG                 Nhãn image đã từng deploy (ví dụ v1.0)
  --env E             Môi trường (mặc định: prod)
  --db-downgrade REV  Chạy `alembic downgrade REV` sau khi hạ image (chỉ khi migration có down)
USAGE
  usage_common
}

TAG=""; ENV_NAME="prod"; PROFILE=""; DB_DOWNGRADE=""
while (($#)); do
  case "$1" in
    --env) ENV_NAME="$2"; shift ;;
    --profile) PROFILE="$2"; shift ;;
    --db-downgrade) DB_DOWNGRADE="$2"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    -*) usage; die "Cờ không hợp lệ: $1" 2 ;;
    *) TAG="${TAG:-$1}" ;;
  esac
  shift
done
[[ -n "${TAG}" ]] || { usage; die "Cần TAG (ví dụ: make rollback TAG=v0.1)" 2; }
[[ "${ENV_NAME}" == "staging" || "${ENV_NAME}" == "prod" ]] || die "--env chỉ nhận staging|prod" 2

load_env_file
HOST="$(resolve_deploy_host "${ENV_NAME}")"
[[ -n "${HOST}" ]] || die "Thiếu DEPLOY_HOST trong .env" 2
PROFILE="${PROFILE:-${DEPLOY_PROFILE:-gpu}}"
REGISTRY="${REGISTRY:-ghcr.io/ctcv}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/ctcv}"
ALEMBIC_WORKDIR="${ALEMBIC_WORKDIR:-/app/services/api}"
SMOKE_BASE_URL="${SMOKE_BASE_URL:-https://${APP_DOMAIN:-localhost}}"
COMPOSE="$(compose_cmd "${PROFILE}")"
APP_SERVICES="api agent speech vision web"

main() {
  timer_start
  log "ROLLBACK ${ENV_NAME} → ${TAG} (host ${HOST})"
  ssh_run "${HOST}" "cd ${DEPLOY_DIR} \
    && $(remote_env_upsert TAG "${TAG}") \
    && REGISTRY=${REGISTRY} TAG=${TAG} ${COMPOSE} pull --quiet ${APP_SERVICES} \
    && REGISTRY=${REGISTRY} TAG=${TAG} ${COMPOSE} up -d --no-deps ${APP_SERVICES}"
  if [[ -n "${DB_DOWNGRADE}" ]]; then
    log "Alembic downgrade ${DB_DOWNGRADE}"
    ssh_run "${HOST}" "cd ${DEPLOY_DIR} && ${COMPOSE} exec -T -w ${ALEMBIC_WORKDIR} api alembic downgrade ${DB_DOWNGRADE}"
  fi
  local args=("${SMOKE_BASE_URL}" --retries 12)
  [[ "${DRY_RUN}" == "1" ]] && args+=(--dry-run)
  if bash "${SCRIPT_DIR}/smoke.sh" "${args[@]}"; then
    local secs; secs="$(timer_elapsed)"
    notify_telegram "↩️ CTCV ${ENV_NAME}: đã quay lui về ${TAG} trong ${secs}s"
    log "XONG trong ${secs}s (mục tiêu ≤ 120 s)"
    ((secs <= 120)) || warn "Rollback mất ${secs}s > 120 s — ghi vào docs/ops/incidents.md"
  else
    notify_telegram "❌ CTCV ${ENV_NAME}: rollback về ${TAG} nhưng smoke test vẫn ĐỎ — cần trực ca"
    die "Rollback xong nhưng smoke test đỏ" 3
  fi
}
main
