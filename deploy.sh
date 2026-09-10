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

# 필수값 확인. 여기서 걸러야 컨테이너가 반쯤 뜬 채로 헤매지 않는다.
set -a; . ./.env; set +a
: "${DOMAIN:?.env 에 DOMAIN 설정 필요}"
: "${POSTGRES_PASSWORD:?.env 에 POSTGRES_PASSWORD 설정 필요}"
: "${SESSION_SECRET:?.env 에 SESSION_SECRET 설정 필요 (openssl rand -hex 32)}"
: "${ADMIN_TOKEN:?.env 에 ADMIN_TOKEN 설정 필요}"

# 실행 환경 확인. 이미지는 전부 멀티아치라 x86/arm 어느 쪽이든 그대로 뜬다.
ARCH="$(uname -m)"
echo "▶ 아키텍처: ${ARCH} / $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}")"
command -v docker >/dev/null || { echo "✗ docker 가 없습니다." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || {
  echo "✗ Docker Compose v2 가 없습니다 (docker-compose v1 은 지원하지 않습니다)." >&2; exit 1; }

# DB 포트는 Tailscale 인터페이스에만 연다. 값이 없으면 루프백으로 떨어진다.
if [ -n "${TAILSCALE_IP:-}" ]; then
  if command -v ip >/dev/null && ! ip -4 addr show 2>/dev/null | grep -q "inet ${TAILSCALE_IP}/"; then
    echo "✗ TAILSCALE_IP(${TAILSCALE_IP}) 가 이 서버의 인터페이스에 없습니다." >&2
    echo "  'tailscale ip -4' 값을 확인하세요 (틀리면 db 컨테이너가 바인딩에 실패합니다)." >&2
    exit 1
  fi
  echo "▶ DB 바인딩: ${TAILSCALE_IP}:5432 (사설망 전용)"
else
  echo "▶ DB 바인딩: 127.0.0.1:5432 (TAILSCALE_IP 미설정 → 루프백)"
fi

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
