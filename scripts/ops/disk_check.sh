#!/usr/bin/env bash
# 디스크 사용률 점검. 임계(기본 85%)를 넘으면 알린다.
# 디스크가 차면 DB 가 쓰기를 멈추고 백업도 실패한다 — 그 전에 알아야 한다.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
ROOT="$(pwd)"
NOTIFY="$ROOT/scripts/ops/notify.sh"
[ -f .env ] && { set -a; . ./.env; set +a; }

THRESHOLD="${DISK_ALERT_PERCENT:-85}"
MOUNT="${DISK_ALERT_MOUNT:-/}"

used=$(df -P "$MOUNT" | awk 'NR==2 {gsub("%","",$5); print $5}')
avail=$(df -Ph "$MOUNT" | awk 'NR==2 {print $4}')

if [ -z "$used" ]; then
  echo "✗ 디스크 사용률을 읽지 못했습니다: $MOUNT" >&2
  exit 1
fi

echo "디스크 $MOUNT: ${used}% 사용, ${avail} 남음 (임계 ${THRESHOLD}%)"
if [ "$used" -ge "$THRESHOLD" ]; then
  "$NOTIFY" "디스크 사용률 ${used}% (임계 ${THRESHOLD}%), 남은 공간 ${avail} — 백업·도커 이미지 정리 필요"
fi
exit 0
