#!/usr/bin/env bash
# 추천 품질 회귀 점검 — 매일 한 번 실데이터로 합의 코스 48개를 만들어 채점한다.
#   ./scripts/ops/quality_check.sh
# 통과율이 기준(QUALITY_FAIL_UNDER, 기본 0.95) 아래로 떨어지거나 오류가 나면 웹훅으로 알린다.
# 결과 JSON 은 data/localdata/eval-YYYYMMDD.json 에 남기고 14일 지난 것은 지운다.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
ROOT="$(pwd)"
NOTIFY="$ROOT/scripts/ops/notify.sh"
[ -f .env ] && ALERT_WEBHOOK_URL="$(grep -E '^ALERT_WEBHOOK_URL=' .env | tail -1 | cut -d= -f2-)" && export ALERT_WEBHOOK_URL

threshold="${QUALITY_FAIL_UNDER:-0.95}"
day="$(date +%Y%m%d)"
out="/data/localdata/eval-$day.json"
log="$(docker compose -f docker-compose.prod.yml exec -T backend nice -n 19 \
  python scripts/eval_consensus.py --out "$out" --fail-under "$threshold" 2>&1)"
code=$?
echo "$log" | tail -25
if [ $code -ne 0 ]; then
  summary="$(echo "$log" | grep -E 'pass_rate|errors|품질 회귀' | tr -s ' ' | tr '\n' ' ')"
  "$NOTIFY" "추천 품질 점검 실패(기준 $threshold): $summary"
fi
find "$ROOT/data/localdata" -name 'eval-*.json' -mtime +14 -delete 2>/dev/null || true
exit $code
