#!/usr/bin/env bash
# DB 백업 — 하루 1회. 압축 보관, 7일 지난 것은 지운다.
#
# 대상은 DB 뿐이다. data/localdata(LOCALDATA CSV, 수백 MB)는 주 1회 다시 받을 수
# 있는 파생 데이터라 백업하지 않는다.
#
# 실패를 조용히 넘기면 "백업이 있는 줄 알았는데 없는" 상태가 된다.
# 어떤 단계에서 실패하든 웹훅으로 알린다.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # 저장소 루트
ROOT="$(pwd)"
NOTIFY="$ROOT/scripts/ops/notify.sh"

[ -f .env ] || { echo "✗ .env 가 없습니다" >&2; exit 1; }
set -a; . ./.env; set +a

# 기본값은 저장소 아래. /var/backups 는 일반 사용자가 못 만든다(크론이 그 사용자로 돈다).
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
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

# 오프사이트 복사 — VM 이 통째로 사라져도(계정 정지·디스크 손상) DB 를 살릴 수 있게
# S3 호환 저장소(Oracle Object Storage 권장)에 한 부 더 둔다. 키가 없으면 건너뛴다.
# rclone 은 설치하지 않고 공식 이미지(arm64 지원)로 돌린다. 설정은 전부 환경변수.
# 보관 기한은 버킷의 수명 주기 규칙(예: 30일 후 삭제)으로 관리한다.
if [ -n "${OFFSITE_S3_BUCKET:-}" ]; then
  : "${OFFSITE_S3_ENDPOINT:?OFFSITE_S3_ENDPOINT 가 없습니다}"
  : "${OFFSITE_S3_ACCESS_KEY:?OFFSITE_S3_ACCESS_KEY 가 없습니다}"
  : "${OFFSITE_S3_SECRET_KEY:?OFFSITE_S3_SECRET_KEY 가 없습니다}"
  if docker run --rm \
      -v "$BACKUP_DIR:/data:ro" \
      -e RCLONE_CONFIG_OFF_TYPE=s3 \
      -e RCLONE_CONFIG_OFF_PROVIDER=Other \
      -e RCLONE_CONFIG_OFF_ENDPOINT="$OFFSITE_S3_ENDPOINT" \
      -e RCLONE_CONFIG_OFF_REGION="${OFFSITE_S3_REGION:-auto}" \
      -e RCLONE_CONFIG_OFF_ACCESS_KEY_ID="$OFFSITE_S3_ACCESS_KEY" \
      -e RCLONE_CONFIG_OFF_SECRET_ACCESS_KEY="$OFFSITE_S3_SECRET_KEY" \
      -e RCLONE_CONFIG_OFF_NO_CHECK_BUCKET=true \
      rclone/rclone:1.68 copyto "/data/$(basename "$target")" \
      "off:$OFFSITE_S3_BUCKET/db/$(basename "$target")" >/dev/null 2>&1; then
    echo "✓ 오프사이트 복사 완료: $OFFSITE_S3_BUCKET/db/$(basename "$target")"
  else
    # 로컬 백업은 성공했으니 지우지 않는다. 알리기만 한다.
    "$NOTIFY" "DB 오프사이트 복사 실패(로컬 백업은 있음): $(basename "$target")"
    echo "✗ 오프사이트 복사 실패" >&2
  fi
fi

# 오래된 백업 정리
deleted=$(find "$BACKUP_DIR" -name 'coursepilot-*.sql.gz' -type f -mtime "+$KEEP_DAYS" -print -delete | wc -l)
[ "$deleted" -gt 0 ] && echo "  오래된 백업 ${deleted}개 삭제(${KEEP_DAYS}일 초과)"
exit 0
