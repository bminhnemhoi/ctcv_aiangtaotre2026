#!/usr/bin/env bash
# Switch traffic to the standby box (or back) by changing the DNS A record — plan §8
# "GPU máy chính chết → chuyển DNS sang máy dự phòng ≤ 5 phút" (`make failover`).
#   bash deploy/scripts/failover.sh [--to backup|primary] [--dry-run]
# Flow: verify the target's /health directly (curl --resolve) → PATCH the Cloudflare DNS
# record (proxied:false = DNS-only, ETH-12) → wait until public DNS answers the new IP →
# smoke test through the domain → Telegram. Cloudflare is a placeholder for any DNS API:
# set DNS_PROVIDER=manual to only print the instruction.
# Needs: APP_DOMAIN, PRIMARY_IP, BACKUP_IP, CF_API_TOKEN, CF_ZONE_ID, CF_RECORD_ID
# (optional CF_RECORD_ID_STATUS for STATUS_DOMAIN).
set -euo pipefail
# shellcheck source=deploy/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  cat <<'USAGE'
Cách dùng: failover.sh [--to backup|primary] [--timeout S] [--dry-run]
  --to backup|primary  Chuyển sang máy dự phòng (mặc định) hoặc quay về máy chính
  --timeout S          Chờ DNS lan truyền tối đa (mặc định 300 s)
USAGE
  usage_common
}

TARGET="backup"; TIMEOUT=300
while (($#)); do
  case "$1" in
    --to) TARGET="$2"; shift ;;
    --timeout) TIMEOUT="$2"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Cờ không hợp lệ: $1" 2 ;;
  esac
  shift
done
[[ "${TARGET}" == "backup" || "${TARGET}" == "primary" ]] || die "--to chỉ nhận backup|primary" 2

load_env_file
require_env APP_DOMAIN PRIMARY_IP BACKUP_IP
DNS_PROVIDER="${DNS_PROVIDER:-cloudflare}"
if [[ "${TARGET}" == "backup" ]]; then TARGET_IP="${BACKUP_IP}"; else TARGET_IP="${PRIMARY_IP}"; fi

resolve_ip() {
  if command -v dig >/dev/null 2>&1; then dig +short "$1" A | tail -n1
  elif command -v getent >/dev/null 2>&1; then getent ahostsv4 "$1" | awk 'NR==1{print $1}'
  else nslookup "$1" 2>/dev/null | awk '/^Address/ {a=$2} END {print a}'
  fi
}

precheck_target() {
  log "Kiểm tra máy đích ${TARGET} (${TARGET_IP}) trực tiếp trước khi chuyển"
  run curl -fsS --max-time 10 -o /dev/null \
    --resolve "${APP_DOMAIN}:443:${TARGET_IP}" "https://${APP_DOMAIN}/health"
}

cloudflare_patch() {
  local record_id="$1" name="$2"
  require_env CF_API_TOKEN CF_ZONE_ID
  local url="https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records/${record_id}"
  local body="{\"type\":\"A\",\"name\":\"${name}\",\"content\":\"${TARGET_IP}\",\"ttl\":60,\"proxied\":false}"
  log "Cloudflare: PATCH bản ghi A ${name} → ${TARGET_IP}, proxied=false (DNS-only, ETH-12)"
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] curl -X PATCH %s -H "Authorization: Bearer ***" --data %s\n' "${url}" "${body}"
    return 0
  fi
  curl -fsS --max-time 20 -o /dev/null -X PATCH "${url}" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json" \
    --data "${body}"
}

update_dns_record() {
  local record_id="$1" name="$2"
  case "${DNS_PROVIDER}" in
    cloudflare) cloudflare_patch "${record_id}" "${name}" ;;
    manual)
      warn "DNS_PROVIDER=manual: đổi bản ghi A ${name} → ${TARGET_IP} (proxied=false) trên bảng DNS rồi Enter"
      [[ "${DRY_RUN}" == "1" ]] || read -r _
      ;;
    *) die "DNS_PROVIDER không hỗ trợ: ${DNS_PROVIDER} (cloudflare|manual)" 2 ;;
  esac
}

wait_dns() {
  local deadline seen
  deadline=$(( $(date +%s) + TIMEOUT ))
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] chờ %s phân giải về %s (tối đa %ss)\n' "${APP_DOMAIN}" "${TARGET_IP}" "${TIMEOUT}"
    return 0
  fi
  while (( $(date +%s) < deadline )); do
    seen="$(resolve_ip "${APP_DOMAIN}")"
    [[ "${seen}" == "${TARGET_IP}" ]] && { log "DNS đã trỏ về ${TARGET_IP}"; return 0; }
    sleep 10
  done
  return 1
}

main() {
  timer_start
  log "FAILOVER → ${TARGET} (${TARGET_IP}) cho ${APP_DOMAIN}"
  precheck_target || die "Máy đích ${TARGET_IP} chưa khỏe (/health) — không chuyển DNS" 3
  update_dns_record "${CF_RECORD_ID:-<CF_RECORD_ID>}" "${APP_DOMAIN}"
  if [[ -n "${STATUS_DOMAIN:-}" && -n "${CF_RECORD_ID_STATUS:-}" ]]; then
    update_dns_record "${CF_RECORD_ID_STATUS}" "${STATUS_DOMAIN}"
  fi
  wait_dns || die "DNS chưa lan truyền sau ${TIMEOUT}s — kiểm tra TTL/bản ghi" 3
  local args=("https://${APP_DOMAIN}" --retries 12)
  [[ "${DRY_RUN}" == "1" ]] && args+=(--dry-run)
  bash "${SCRIPT_DIR}/smoke.sh" "${args[@]}" || die "Smoke test qua domain đỏ sau failover" 3
  local secs; secs="$(timer_elapsed)"
  notify_telegram "🔀 CTCV: đã chuyển ${APP_DOMAIN} sang máy ${TARGET} (${TARGET_IP}) trong ${secs}s"
  log "XONG trong ${secs}s (mục tiêu ≤ 300 s) — ghi vào docs/ops/incidents.md"
  ((secs <= 300)) || warn "Failover mất ${secs}s > 300 s"
}
main
