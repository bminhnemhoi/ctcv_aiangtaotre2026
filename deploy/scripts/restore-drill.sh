#!/usr/bin/env bash
# Restore drill (plan §8, `make restore-drill`, before T-72h): restore the newest PostgreSQL
# dump into a throw-away compose project, count rows in `sessions`, compare with the live
# stack when reachable, then destroy the temporary project and its volumes.
#   bash deploy/scripts/restore-drill.sh [--dump FILE] [--keep] [--dry-run]
set -euo pipefail
# shellcheck source=deploy/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  cat <<'USAGE'
Cách dùng: restore-drill.sh [--dump FILE] [--keep] [--profile gpu|cpu] [--dry-run]
  --dump FILE   Bản dump cụ thể (mặc định: mới nhất trong BACKUP_DIR/pg)
  --keep        Giữ lại project tạm để xem bằng tay (mặc định: xóa cả volume)
USAGE
  usage_common
}

DUMP=""; KEEP_PROJECT=0; PROFILE=""
while (($#)); do
  case "$1" in
    --dump) DUMP="$2"; shift ;;
    --keep) KEEP_PROJECT=1 ;;
    --profile) PROFILE="$2"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Cờ không hợp lệ: $1" 2 ;;
  esac
  shift
done

load_env_file
PROFILE="${PROFILE:-${DEPLOY_PROFILE:-gpu}}"
BACKUP_DIR="${BACKUP_DIR:-${REPO_ROOT}/deploy/backups}"
PG_USER="${POSTGRES_USER:-ctcv}"
PG_DB="${POSTGRES_DB:-ctcv}"
PROJECT="ctcv-restore-$(date -u +%Y%m%d%H%M%S)"
TMP_COMPOSE="docker compose -p ${PROJECT} --env-file .env -f ${COMPOSE_BASE}"
LIVE_COMPOSE="$(compose_cmd "${PROFILE}")"
cd "${REPO_ROOT}"

pick_dump() {
  if [[ -n "${DUMP}" ]]; then printf '%s' "${DUMP}"; return; fi
  newest_file "${BACKUP_DIR}/pg" '*.dump'
}

wait_pg() {
  local i
  for ((i = 1; i <= 30; i++)); do
    if run_sh "${TMP_COMPOSE} exec -T postgres pg_isready -U '${PG_USER}' -d '${PG_DB}' >/dev/null"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# count_rows "<compose cmd>": rows in sessions, "n/a" when the stack is unreachable.
count_rows() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] %s exec -T postgres psql -tAc "select count(*) from sessions"\n' "$1" >&2
    printf '0'
    return
  fi
  $1 exec -T postgres psql -U "${PG_USER}" -d "${PG_DB}" -tAc "select count(*) from sessions" 2>/dev/null \
    | tr -d '[:space:]' || printf 'n/a'
}

cleanup() {
  if [[ "${KEEP_PROJECT}" == "1" ]]; then
    warn "Giữ project ${PROJECT} (--keep): xóa bằng '${TMP_COMPOSE} down -v'"
    return
  fi
  log "Dọn project tạm ${PROJECT} (down -v)"
  run_sh "${TMP_COMPOSE} down -v --remove-orphans >/dev/null 2>&1 || true"
}

verify_checksum() {
  local dump="$1"
  [[ "${DRY_RUN}" == "1" || ! -f "${dump}.sha256" ]] && return 0
  run_sh "cd '$(dirname "${dump}")' && sha256sum -c '$(basename "${dump}").sha256'"
}

main() {
  timer_start
  local dump; dump="$(pick_dump)"
  if [[ -z "${dump}" ]]; then
    [[ "${DRY_RUN}" == "1" ]] || die "Không có bản dump nào trong ${BACKUP_DIR}/pg — chạy make backup trước" 2
    dump="${BACKUP_DIR}/pg/<newest>.dump"
  fi
  log "RESTORE DRILL từ ${dump##*/} vào project tạm ${PROJECT}"
  verify_checksum "${dump}"
  trap cleanup EXIT
  run_sh "${TMP_COMPOSE} up -d postgres"
  wait_pg || die "Postgres tạm không sẵn sàng" 3
  run_sh "${TMP_COMPOSE} exec -T postgres pg_restore -U '${PG_USER}' -d '${PG_DB}' --no-owner --clean --if-exists --exit-on-error < '${dump}'"
  local restored live
  restored="$(count_rows "${TMP_COMPOSE}")"
  live="$(count_rows "${LIVE_COMPOSE}")"
  log "sessions: bản khôi phục = ${restored}; đang chạy = ${live}"
  if [[ "${DRY_RUN}" != "1" && "${live}" != "n/a" && "${restored}" != "${live}" ]]; then
    warn "Số dòng lệch (dump cũ hơn dữ liệu sống là bình thường; lệch lớn → kiểm tra cron backup)"
  fi
  log "RESTORE DRILL ĐẠT trong $(timer_elapsed)s — ghi kết quả vào docs/ops/RUNBOOK.md §3 / DAILY.md"
}
main
