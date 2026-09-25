#!/usr/bin/env bash
# Smoke test after a deploy/rollback/failover (plan §8): loop on /v1/health until 200, then
# GET /v1/scenarios must list every shipped scenario id (sandbox/scenarios/*.json; E01 = 1,
# E02 = 4, E10 = 12). Called by deploy.sh; usable alone:
#   bash deploy/scripts/smoke.sh https://app.example.vn [--retries 24] [--min-scenarios 1] [--dry-run]
set -euo pipefail
# shellcheck source=deploy/scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() {
  cat <<'USAGE'
Cách dùng: smoke.sh <BASE_URL> [--retries N] [--interval S] [--min-scenarios N] [--dry-run]
  BASE_URL          Ví dụ https://app.example.vn hoặc http://127.0.0.1:8000
  --retries N       Số lần thử /v1/health (mặc định 24 ≈ 2 phút)
  --interval S      Giây giữa hai lần thử (mặc định 5)
  --min-scenarios N Số kịch bản tối thiểu khi chưa có sandbox/scenarios (mặc định 1)
USAGE
  usage_common
}

BASE_URL=""; RETRIES=24; INTERVAL=5; MIN_SCENARIOS=1
while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --retries) RETRIES="$2"; shift ;;
    --interval) INTERVAL="$2"; shift ;;
    --min-scenarios) MIN_SCENARIOS="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) die "Cờ không hợp lệ: $1" 2 ;;
    *) BASE_URL="${BASE_URL:-$1}" ;;
  esac
  shift
done
[[ -n "${BASE_URL}" ]] || { usage; die "Thiếu BASE_URL" 2; }
BASE_URL="${BASE_URL%/}"

wait_health() {
  local i
  for ((i = 1; i <= RETRIES; i++)); do
    if [[ "${DRY_RUN}" == "1" ]]; then
      printf '[dry-run] curl -fsS %s/v1/health (lần %d/%d)\n' "${BASE_URL}" "${i}" "${RETRIES}"
      return 0
    fi
    if curl -fsS --max-time 10 "${BASE_URL}/v1/health" >/dev/null 2>&1; then
      log "smoke: /v1/health OK sau ${i} lần thử"
      return 0
    fi
    sleep "${INTERVAL}"
  done
  return 1
}

check_scenarios() {
  local body count expected id missing=()
  mapfile -t expected < <(scenario_ids)
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] curl -fsS %s/v1/scenarios → mong đợi %d kịch bản: %s\n' \
      "${BASE_URL}" "${#expected[@]}" "${expected[*]:-(>= ${MIN_SCENARIOS})}"
    return 0
  fi
  body="$(curl -fsS --max-time 20 "${BASE_URL}/v1/scenarios")" || return 1
  count="$(printf '%s' "${body}" | grep -o '"id"' | wc -l | tr -d ' ')"
  for id in "${expected[@]}"; do
    grep -q "\"${id}\"" <<<"${body}" || missing+=("${id}")
  done
  if ((${#missing[@]})); then
    warn "smoke: thiếu kịch bản trong /v1/scenarios: ${missing[*]}"
    return 1
  fi
  if ((count < MIN_SCENARIOS)); then
    warn "smoke: /v1/scenarios trả ${count} kịch bản (< ${MIN_SCENARIOS})"
    return 1
  fi
  log "smoke: /v1/scenarios OK (${count} kịch bản, đủ ${#expected[@]} id đã ship)"
}

log "smoke test ${BASE_URL}"
wait_health || die "smoke: /v1/health không xanh sau ${RETRIES} lần" 3
check_scenarios || die "smoke: /v1/scenarios không đạt" 3
log "smoke: ĐẠT"
