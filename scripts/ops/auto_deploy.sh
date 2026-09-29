#!/usr/bin/env bash
# main 에 새 커밋이 머지되면 VM 이 스스로 받아 배포한다(크론 5분마다).
#
# GitHub → SSH 로 밀어 넣지 않고 VM 이 당겨 오므로 SSH 키를 어디에도 맡기지 않는다.
# 배포는 커밋 sha 태그 이미지로 고정한다(latest 는 굽는 중에 바뀔 수 있다).
# 실패하면 직전 배포 sha 로 되돌리고 알린다. 실패한 sha 는 다시 시도하지 않는다.
# 끄려면 .env 에 AUTO_DEPLOY=false.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # 저장소 루트
ROOT="$(pwd)"
NOTIFY="$ROOT/scripts/ops/notify.sh"
STATE="$ROOT/.deploy"
mkdir -p "$STATE"

# 겹쳐 돌면 안 된다(배포가 5분을 넘길 수 있다).
# 크론은 겹치면 그냥 빠지고, GitHub 에서 부른 배포(--wait, deploy_hook.sh)는 앞 배포가 끝날 때까지 기다린다.
exec 9>"$STATE/lock"
if [ "${1:-}" = "--wait" ]; then
  flock -w 900 9 || { echo "✗ 앞선 배포가 15분 넘게 끝나지 않음" >&2; exit 1; }
else
  flock -n 9 || exit 0
fi

if [ -f .env ]; then
  AUTO_DEPLOY="$(grep -E '^AUTO_DEPLOY=' .env | tail -1 | cut -d= -f2)"
fi
[ "${AUTO_DEPLOY:-true}" = "false" ] && exit 0

git fetch -q origin main || { echo "✗ git fetch 실패" >&2; exit 1; }
target="$(git rev-parse origin/main)"
current="$(cat "$STATE/deployed" 2>/dev/null || git rev-parse HEAD)"
[ "$target" = "$current" ] && exit 0
[ "$(cat "$STATE/failed" 2>/dev/null)" = "$target" ] && exit 0  # 이미 실패·복구한 커밋

# 사람이 VM 에서 고치는 중이면 덮어쓰지 않는다
if ! git diff --quiet || ! git diff --cached --quiet; then
  "$NOTIFY" "자동 배포 보류: VM 저장소에 커밋 안 된 수정이 있습니다(${target:0:7})"
  echo "$target" > "$STATE/failed"
  exit 1
fi

echo "$(date '+%F %T') ▶ 배포 ${current:0:7} → ${target:0:7}"
git checkout -q --detach "$target"
if DEPLOY_TAG="$target" ./deploy.sh; then
  echo "$target" > "$STATE/deployed"
  rm -f "$STATE/failed"
  "$NOTIFY" "배포 완료: ${target:0:7} $(git log -1 --format=%s "$target")"
  exit 0
fi

echo "$(date '+%F %T') ✗ 배포 실패 → ${current:0:7} 로 되돌림" >&2
echo "$target" > "$STATE/failed"
git checkout -q --detach "$current"
if DEPLOY_TAG="$current" ./deploy.sh; then
  "$NOTIFY" "배포 실패, 이전 버전(${current:0:7})으로 되돌림: ${target:0:7}"
else
  "$NOTIFY" "🚨 배포 실패 + 되돌리기도 실패: ${target:0:7} → ${current:0:7}. 즉시 확인 필요"
fi
exit 1
