#!/usr/bin/env bash
# crontab.txt 를 현재 사용자 crontab 에 설치한다(기존 CoursePilot 항목은 교체).
# deploy.sh 가 부르지만, 손으로도 돌릴 수 있다.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
ROOT="$(pwd)"
SRC="$ROOT/scripts/ops/crontab.txt"
MARK_BEGIN="# >>> coursepilot >>>"
MARK_END="# <<< coursepilot <<<"

command -v crontab >/dev/null || { echo "✗ crontab 이 없습니다(cron 설치 필요)" >&2; exit 1; }

# 로그·백업은 저장소 아래에 둔다. /var/log 로 만들면 root 소유가 되고, 크론은
# 일반 사용자로 돌기 때문에 >> 리다이렉트가 권한 거부로 죽는다 — 잡 5개가
# 전부 조용히 실행되지 않는다.
mkdir -p "$ROOT/logs" "$ROOT/backups"
# 예전 설치본이 root 소유로 만들어 뒀을 수 있다
if [ ! -w "$ROOT/logs" ] || [ ! -w "$ROOT/backups" ]; then
  sudo chown -R "$(id -u):$(id -g)" "$ROOT/logs" "$ROOT/backups" 2>/dev/null || true
fi
for dir in "$ROOT/logs" "$ROOT/backups"; do
  [ -w "$dir" ] || { echo "✗ $dir 에 쓸 수 없습니다(소유자 확인: ls -ld $dir)" >&2; exit 1; }
done

block="$(sed "s|{{ROOT}}|$ROOT|g" "$SRC")"
current="$(crontab -l 2>/dev/null || true)"
# 이전에 설치한 블록만 걷어내고 나머지 사용자 항목은 그대로 둔다
kept="$(printf '%s\n' "$current" | sed "/$MARK_BEGIN/,/$MARK_END/d")"

printf '%s\n%s\n%s\n%s\n' "$kept" "$MARK_BEGIN" "$block" "$MARK_END" \
  | sed '/^$/N;/^\n$/D' | crontab -

echo "✓ 크론 설치 완료 (crontab -l 로 확인)"
crontab -l | sed -n "/$MARK_BEGIN/,/$MARK_END/p" | grep -c '^[0-9*]' | xargs -I{} echo "  등록된 작업 {}개"
