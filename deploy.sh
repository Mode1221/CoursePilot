#!/usr/bin/env bash
# CoursePilot 원커맨드 배포 (단일 VM, docker compose).
#   전제: Docker + Docker Compose v2 설치, .env 작성(.env.prod.example 참고),
#         DNS 에서 DOMAIN 과 api.DOMAIN 이 이 서버 IP 를 가리키도록 A 레코드 설정,
#         방화벽/보안그룹에서 80, 443 오픈.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "✗ .env 가 없습니다. 'cp .env.prod.example .env' 후 값을 채우세요." >&2
  exit 1
fi

# DOMAIN / POSTGRES_PASSWORD 필수값 확인
set -a; . ./.env; set +a
: "${DOMAIN:?.env 에 DOMAIN 설정 필요}"
: "${POSTGRES_PASSWORD:?.env 에 POSTGRES_PASSWORD 설정 필요}"

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "▶ 빌드 & 기동 (${DOMAIN})..."
$COMPOSE pull db caddy || true
$COMPOSE up -d --build

echo "▶ 백엔드 헬스체크 대기..."
for i in $(seq 1 30); do
  if $COMPOSE exec -T backend python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health'); " 2>/dev/null; then
    echo "✓ 백엔드 정상"
    break
  fi
  sleep 2
  [ "$i" = "30" ] && { echo "✗ 백엔드 헬스체크 실패"; $COMPOSE logs --tail=50 backend; exit 1; }
done

echo "✓ 배포 완료"
echo "   프론트:  https://${DOMAIN}"
echo "   API:     https://api.${DOMAIN}/health"
echo "   (최초 접속 시 Caddy 가 HTTPS 인증서를 자동 발급합니다. 수십 초 소요될 수 있음)"
