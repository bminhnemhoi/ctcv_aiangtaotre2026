#!/usr/bin/env bash
# Deploy CTCV to staging|prod (plan §8, brief §10 `make deploy ENV=`):
#   [make check] → [build+push images :TAG] → rsync deploy/ → ssh: compose pull && up -d
#   → alembic upgrade head → smoke test (/v1/health + /v1/scenarios) → status push → Telegram.
# Usage:
#   bash deploy/scripts/deploy.sh <staging|prod> [--tag vX.Y] [--profile gpu|cpu]
#        [--skip-check] [--no-build] [--auto-rollback] [--dry-run]
# CI (release.yml) calls it with --skip-check --no-build after pushing images itself.
# Needs in .env / CI secrets: DEPLOY_HOST (or DEPLOY_HOST_STAGING/PROD), DEPLOY_USER,
# DEPLOY_DIR, REGISTRY, APP_DOMAIN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional:
# SSH_KEY_FILE, UPTIME_KUMA_PUSH_URL, SMOKE_BASE_URL, ALEMBIC_WORKDIR).
set -euo pipefail
# shellcheck source=deploy/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  cat <<'USAGE'
Cách dùng: deploy.sh <staging|prod> [--tag TAG] [--profile gpu|cpu] [--skip-check] [--no-build]
                     [--auto-rollback] [--dry-run]
  --tag TAG        Nhãn image (mặc định: git describe --tags)
  --profile P      Compose profile trên máy chủ (mặc định: gpu; VPS CPU luôn bật: cpu)
  --skip-check     Không chạy `make check` (CI đã chạy)
  --no-build       Không build/push image (CI đã push)
  --auto-rollback  Smoke test đỏ → tự chạy rollback.sh về tag đang chạy trước đó
USAGE
  usage_common
}

ENV_NAME=""; TAG=""; PROFILE=""; SKIP_CHECK=0; NO_BUILD=0; AUTO_ROLLBACK=0
while (($#)); do
  case "$1" in
    staging|prod) ENV_NAME="$1" ;;
    --tag) TAG="$2"; shift ;;
    --profile) PROFILE="$2"; shift ;;
    --skip-check) SKIP_CHECK=1 ;;
    --no-build) NO_BUILD=1 ;;
    --auto-rollback) AUTO_ROLLBACK=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Tham số không hợp lệ: $1 (chỉ nhận staging|prod)" 2 ;;
  esac
  shift
done
[[ -n "${ENV_NAME}" ]] || { usage; die "Cần môi trường: staging hoặc prod" 2; }

load_env_file
HOST="$(resolve_deploy_host "${ENV_NAME}")"
[[ -n "${HOST}" ]] || die "Thiếu DEPLOY_HOST (hoặc DEPLOY_HOST_${ENV_NAME^^}) trong .env" 2
TAG="${TAG:-$(git_default_tag)}"
PROFILE="${PROFILE:-${DEPLOY_PROFILE:-gpu}}"
REGISTRY="${REGISTRY:-ghcr.io/ctcv}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/ctcv}"
ALEMBIC_WORKDIR="${ALEMBIC_WORKDIR:-/app/services/api}"
SMOKE_BASE_URL="${SMOKE_BASE_URL:-https://${APP_DOMAIN:-localhost}}"
COMPOSE="$(compose_cmd "${PROFILE}")"
SERVICES=(api agent speech vision web)

step_check() {
  if [[ "${SKIP_CHECK}" == "1" ]]; then log "Bỏ qua make check (--skip-check)"; return; fi
  log "make check đầy đủ trước khi deploy (D13)"
  run make -C "${REPO_ROOT}" check
}

step_build_push() {
  if [[ "${NO_BUILD}" == "1" ]]; then log "Bỏ qua build/push (--no-build)"; return; fi
  log "Build image có nhãn ${TAG} (context = gốc repo, D14) và đẩy lên ${REGISTRY}"
  local svc
  for svc in "${SERVICES[@]}"; do
    run docker build -f "${REPO_ROOT}/deploy/docker/${svc}.Dockerfile" \
      -t "${REGISTRY}/ctcv-${svc}:${TAG}" "${REPO_ROOT}"
    run docker push "${REGISTRY}/ctcv-${svc}:${TAG}"
  done
}

current_remote_tag() {
  if [[ "${DRY_RUN}" == "1" ]]; then printf 'previous'; return; fi
  ssh_run "${HOST}" "cd ${DEPLOY_DIR} && grep -E '^TAG=' .env | cut -d= -f2" 2>/dev/null || true
}

step_remote_up() {
  log "Đồng bộ deploy/ → ${HOST}:${DEPLOY_DIR}/deploy"
  rsync_deploy_dir "${HOST}"
  # TAG and COMPOSE_PROFILES land in the host .env: compose interpolation reads them and the
  # agent container picks planner vs planner_small from COMPOSE_PROFILES (D29).
  log "Ghi TAG=${TAG}, COMPOSE_PROFILES=${PROFILE} vào env máy chủ rồi: compose pull && up -d"
  ssh_run "${HOST}" "cd ${DEPLOY_DIR} \
    && $(remote_env_upsert TAG "${TAG}") \
    && $(remote_env_upsert COMPOSE_PROFILES "${PROFILE}") \
    && REGISTRY=${REGISTRY} TAG=${TAG} ${COMPOSE} pull --quiet \
    && REGISTRY=${REGISTRY} TAG=${TAG} ${COMPOSE} up -d --remove-orphans"
  log "Migration: docker compose exec api alembic upgrade head"
  ssh_run "${HOST}" "cd ${DEPLOY_DIR} && ${COMPOSE} exec -T -w ${ALEMBIC_WORKDIR} api alembic upgrade head"
}

step_smoke() {
  log "smoke test ${SMOKE_BASE_URL} (/v1/health + /v1/scenarios)"
  local args=("${SMOKE_BASE_URL}")
  [[ "${DRY_RUN}" == "1" ]] && args+=(--dry-run)
  bash "${SCRIPT_DIR}/smoke.sh" "${args[@]}"
}

step_status_page() {
  if [[ -n "${UPTIME_KUMA_PUSH_URL:-}" ]]; then
    log "Cập nhật status page (Uptime Kuma push monitor)"
    run_sh "curl -fsS --max-time 10 -o /dev/null '${UPTIME_KUMA_PUSH_URL}?status=up&msg=deploy+${TAG}'"
  else
    log "UPTIME_KUMA_PUSH_URL chưa đặt — status page tự cập nhật qua monitor /health"
  fi
}

rollback_previous() {
  local previous="$1"
  local args=("${previous}" --env "${ENV_NAME}" --profile "${PROFILE}")
  [[ "${DRY_RUN}" == "1" ]] && args+=(--dry-run)
  warn "Tự quay lui về ${previous}"
  bash "${SCRIPT_DIR}/rollback.sh" "${args[@]}"
}

main() {
  timer_start
  log "DEPLOY ${ENV_NAME} ← ${TAG} (host ${HOST}, profile ${PROFILE})"
  step_check
  step_build_push
  local previous_tag; previous_tag="$(current_remote_tag)"
  step_remote_up
  if ! step_smoke; then
    notify_telegram "❌ CTCV ${ENV_NAME}: deploy ${TAG} smoke test ĐỎ (trước đó: ${previous_tag:-?})"
    if [[ "${AUTO_ROLLBACK}" == "1" && -n "${previous_tag}" ]]; then rollback_previous "${previous_tag}"; fi
    die "Deploy thất bại — xem log trên và docs/ops/RUNBOOK.md §3 (make rollback TAG=${previous_tag:-<tag cũ>})" 3
  fi
  step_status_page
  notify_telegram "✅ CTCV ${ENV_NAME}: đã deploy ${TAG} trong $(timer_elapsed)s (${SMOKE_BASE_URL})"
  log "XONG trong $(timer_elapsed)s"
}
main
