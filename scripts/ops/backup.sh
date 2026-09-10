#!/usr/bin/env bash
# DB 백업 — 하루 1회. 압축 보관, 7일 지난 것은 지운다.
#
# 실패를 조용히 넘기면 "백업이 있는 줄 알았는데 없는" 상태가 된다.
# 어떤 단계에서 실패하든 웹훅으로 알린다.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # 저장소 루트
ROOT="$(pwd)"
NOTIFY="$ROOT/scripts/ops/notify.sh"

[ -f .env ] || { echo "✗ .env 가 없습니다" >&2; exit 1; }
set -a; . ./.env; set +a

BACKUP_DIR="${BACKUP_DIR:-/var/backups/coursepilot}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
DB_USER="${POSTGRES_USER:-coursepilot}"
DB_NAME="${POSTGRES_DB:-coursepilot}"
COMPOSE="docker compose -f $ROOT/docker-compose.prod.yml"

stamp="$(date +%Y%m%d-%H%M%S)"
target="$BACKUP_DIR/coursepilot-$stamp.sql.gz"
tmp="$target.part"

fail() {
  rm -f "$tmp"
  echo "✗ $1" >&2
  "$NOTIFY" "DB 백업 실패: $1"
  exit 1
}

mkdir -p "$BACKUP_DIR" || fail "백업 디렉터리를 만들 수 없습니다: $BACKUP_DIR"

# 파이프 중간(pg_dump)이 실패해도 잡아야 한다 → PIPESTATUS 확인
$COMPOSE exec -T db pg_dump -U "$DB_USER" "$DB_NAME" 2>/dev/null | gzip -c > "$tmp"
status=("${PIPESTATUS[@]}")
[ "${status[0]}" -eq 0 ] || fail "pg_dump 실패(코드 ${status[0]})"
[ "${status[1]}" -eq 0 ] || fail "gzip 실패(코드 ${status[1]})"

# 빈 파일이 남으면 백업이 있는 줄 알게 된다 — 크기를 확인한다
size=$(stat -c%s "$tmp" 2>/dev/null || echo 0)
[ "$size" -ge 1024 ] || fail "백업 파일이 너무 작습니다(${size}B)"

mv "$tmp" "$target"
echo "✓ 백업 완료: $target ($((size / 1024))KB)"

# 오래된 백업 정리
deleted=$(find "$BACKUP_DIR" -name 'coursepilot-*.sql.gz' -type f -mtime "+$KEEP_DAYS" -print -delete | wc -l)
[ "$deleted" -gt 0 ] && echo "  오래된 백업 ${deleted}개 삭제(${KEEP_DAYS}일 초과)"
exit 0
