#!/usr/bin/env bash
# Backup (plan §8, ADR-005): PostgreSQL dump on EVERY run (cron every 6 h) + Qdrant snapshot
# (once per day, or --qdrant to force) → BACKUP_DIR, then off-site copy (rclone remote in
# BACKUP_REMOTE — an in-country object storage, ETH-12) and rotation to 14 copies.
# Screenshots are never backed up (MinIO TTL 60 s). Runs on the host next to the stack:
#   bash deploy/scripts/backup.sh [--qdrant] [--keep 14] [--dry-run]
# cron:  0 */6 * * *  cd /opt/ctcv && bash deploy/scripts/backup.sh >> /var/log/ctcv-backup.log 2>&1
set -euo pipefail
# shellcheck source=deploy/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  cat <<'USAGE'
Cách dùng: backup.sh [--qdrant] [--keep N] [--profile gpu|cpu] [--dry-run]
  --qdrant      Ép chụp snapshot Qdrant ngay (mặc định: 1 lần/ngày)
  --keep N      Số bản giữ lại cho mỗi loại (mặc định 14 — ADR-005)
USAGE
  usage_common
}

FORCE_QDRANT=0; KEEP=14; PROFILE=""
while (($#)); do
  case "$1" in
    --qdrant) FORCE_QDRANT=1 ;;
    --keep) KEEP="$2"; shift ;;
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
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
COMPOSE="$(compose_cmd "${PROFILE}")"
# Qdrant's REST call is made from inside its own container (the image has bash, no curl).
QDRANT_SNAPSHOT_REQ='exec 3<>/dev/tcp/127.0.0.1/6333; printf "POST /snapshots HTTP/1.1\r\nHost: qdrant\r\nContent-Length: 0\r\nConnection: close\r\n\r\n" >&3; tail -c 400 <&3'
cd "${REPO_ROOT}"

backup_postgres() {
  local out="${BACKUP_DIR}/pg/ctcv-${STAMP}.dump"
  log "pg_dump ${PG_DB} → ${out#"${REPO_ROOT}"/}"
  run mkdir -p "${BACKUP_DIR}/pg"
  run_sh "${COMPOSE} exec -T postgres pg_dump -U '${PG_USER}' -d '${PG_DB}' -Fc --no-owner > '${out}'"
  run_sh "test -s '${out}' && sha256sum '${out}' > '${out}.sha256'"
}

qdrant_due() {
  [[ "${FORCE_QDRANT}" == "1" ]] && return 0
  local latest
  latest="$(newest_file "${BACKUP_DIR}/qdrant" '*.snapshot')"
  [[ -z "${latest}" ]] && return 0
  # Due when the newest local snapshot is older than 24 h.
  [[ -n "$(find "${latest}" -mmin +1440 2>/dev/null)" ]]
}

backup_qdrant() {
  if ! qdrant_due; then log "Qdrant: snapshot hôm nay đã có — bỏ qua"; return 0; fi
  log "Qdrant: tạo snapshot toàn bộ và chép ra ${BACKUP_DIR#"${REPO_ROOT}"/}/qdrant"
  run mkdir -p "${BACKUP_DIR}/qdrant"
  run_sh "${COMPOSE} exec -T qdrant bash -c '${QDRANT_SNAPSHOT_REQ}'"
  run_sh "name=\$(${COMPOSE} exec -T qdrant bash -c 'ls -1t /qdrant/snapshots/*.snapshot | head -n1'); \
    ${COMPOSE} cp \"qdrant:\${name}\" '${BACKUP_DIR}/qdrant/'; \
    ${COMPOSE} exec -T qdrant bash -c 'ls -1t /qdrant/snapshots/*.snapshot | tail -n +3 | xargs -r rm -f'"
}

offsite_copy() {
  if [[ -z "${BACKUP_REMOTE:-}" ]]; then
    warn "BACKUP_REMOTE chưa đặt (rclone remote:path, object storage trong nước) — bản sao chỉ nằm trên máy này"
    return 0
  fi
  log "Chép off-site → ${BACKUP_REMOTE}"
  run rclone copy --max-age 7h "${BACKUP_DIR}/pg" "${BACKUP_REMOTE}/pg"
  run rclone copy --max-age 25h "${BACKUP_DIR}/qdrant" "${BACKUP_REMOTE}/qdrant"
}

rotate() {
  local kind="$1" pattern="$2"
  log "Xoay vòng ${kind}: giữ ${KEEP} bản mới nhất"
  run_sh "ls -1t ${BACKUP_DIR}/${kind}/${pattern} 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f"
  run_sh "ls -1t ${BACKUP_DIR}/${kind}/*.sha256 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f"
  if [[ -n "${BACKUP_REMOTE:-}" ]]; then
    run rclone delete --min-age "$((KEEP * 6))h" "${BACKUP_REMOTE}/${kind}"
  fi
}

main() {
  timer_start
  log "BACKUP ${STAMP} (giữ ${KEEP} bản)"
  backup_postgres
  backup_qdrant
  offsite_copy
  rotate pg '*.dump'
  rotate qdrant '*.snapshot'
  log "XONG trong $(timer_elapsed)s"
}
if ! main; then
  notify_telegram "❌ CTCV backup ${STAMP} thất bại — kiểm tra log trên máy chủ"
  exit 1
fi
