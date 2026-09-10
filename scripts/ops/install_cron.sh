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
sudo mkdir -p /var/log/coursepilot 2>/dev/null || mkdir -p /var/log/coursepilot 2>/dev/null || true

block="$(sed "s|{{ROOT}}|$ROOT|g" "$SRC")"
current="$(crontab -l 2>/dev/null || true)"
# 이전에 설치한 블록만 걷어내고 나머지 사용자 항목은 그대로 둔다
kept="$(printf '%s\n' "$current" | sed "/$MARK_BEGIN/,/$MARK_END/d")"

printf '%s\n%s\n%s\n%s\n' "$kept" "$MARK_BEGIN" "$block" "$MARK_END" \
  | sed '/^$/N;/^\n$/D' | crontab -

echo "✓ 크론 설치 완료 (crontab -l 로 확인)"
crontab -l | sed -n "/$MARK_BEGIN/,/$MARK_END/p" | grep -c '^[0-9*]' | xargs -I{} echo "  등록된 작업 {}개"
