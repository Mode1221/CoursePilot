#!/usr/bin/env bash
# 운영 알림 한 줄 보내기. ALERT_WEBHOOK_URL 이 없으면 로그로만 남긴다.
#   scripts/ops/notify.sh "백업 실패: ..."
set -uo pipefail

msg="${1:-(내용 없음)}"
host="$(hostname)"
text="[CoursePilot/${host}] ${msg}"

if [ -n "${ALERT_WEBHOOK_URL:-}" ]; then
  # 알림 실패가 호출한 쪽을 죽이면 안 된다(백업 실패보다 알림 실패가 덜 급하다)
  curl -sS -m 10 -X POST -H "Content-Type: application/json" \
    -d "$(printf '{"text":%s,"kind":"ops","target":"%s"}' \
          "$(printf '%s' "$text" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')" \
          "$host")" \
    "$ALERT_WEBHOOK_URL" >/dev/null || echo "알림 발송 실패: $text" >&2
else
  echo "알림(웹훅 미설정): $text"
fi
