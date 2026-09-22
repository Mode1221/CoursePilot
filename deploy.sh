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

# .env 는 bash 로 읽는다(compose 와 달리 셸 규칙이 적용된다).
# 값에 따옴표 없는 공백·#·$·` 가 있으면 잘리거나 다른 것으로 치환된다 —
# 비밀번호가 조용히 반토막 나면 원인을 찾기 어렵다. 먼저 훑어서 경고한다.
# (예전 패턴의 \t 가 대괄호 안에서 글자 't' 로 읽혀 't' 가 든 모든 값을 잡았다 — [[:space:]] 로.
#  값 없이 주석만 붙은 줄 'KEY=   # 설명' 은 해석이 달라지지 않으므로 제외.)
risky="$(grep -nE '^[A-Z_][A-Z0-9_]*=' .env \
  | grep -vE "^[0-9]+:[A-Z_][A-Z0-9_]*='[^']*'$" \
  | grep -vE '^[0-9]+:[A-Z_][A-Z0-9_]*=[[:space:]]*(#.*)?$' \
  | grep -E '^[0-9]+:[A-Z_][A-Z0-9_]*=.*[[:space:]#$`\\"]' || true)"
if [ -n "$risky" ]; then
  echo "⚠ .env 에 셸이 다르게 해석할 문자가 있습니다(공백·#·\$·\`·큰따옴표):" >&2
  echo "$risky" >&2
  echo "  값은 따옴표 없이, 공백 없이 쓰거나 전체를 '작은따옴표'로 감싸세요." >&2
  echo "  큰따옴표는 source 될 때 벗겨집니다 — JSON 값은 반드시 작은따옴표로." >&2
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

# 머지 직후 배포하면 CI(Release images)가 아직 이미지를 굽는 중일 수 있다(2~3분).
# 태그가 없으면 바로 실패하지 말고 준비될 때까지 기다린다. IMAGE_WAIT_SEC 로 조절(기본 600초).
# 그래도 없으면 GHCR 비공개(로그인 필요)이거나 빌드가 실패한 것이다.
wait_for_image() {
  local ref="$1" waited=0 limit="${IMAGE_WAIT_SEC:-600}"
  until docker manifest inspect "$ref" >/dev/null 2>&1; do
    if [ "$waited" -ge "$limit" ]; then return 1; fi
    [ "$waited" -eq 0 ] && echo "… 이미지를 기다리는 중: $ref (CI 가 굽는 중일 수 있음, 최대 ${limit}초)"
    sleep 15; waited=$((waited + 15))
  done
  [ "$waited" -gt 0 ] && echo "✓ 이미지 준비됨 (${waited}초 대기)"
  return 0
}
for svc in backend frontend; do
  ref="${IMAGE_REGISTRY:-ghcr.io/mode1221/coursepilot}-${svc}:${IMAGE_TAG:-latest}"
  wait_for_image "$ref" || { missing_ref="$ref"; break; }
done
if [ -n "${missing_ref:-}" ]; then
  echo "✗ 이미지를 볼 수 없습니다: ${missing_ref}" >&2
  echo "  · CI(Release images)가 아직 안 돌았거나," >&2
  echo "  · GHCR 패키지가 비공개입니다 → 다음 중 하나:" >&2
  echo "      docker login ghcr.io -u <github-id>   # read:packages 권한 PAT" >&2
  echo "      또는 GitHub 패키지 설정에서 public 으로 전환" >&2
  exit 1
fi

# 배치가 도는 중이면 기다린다. 배치 도중에 컨테이너를 갈아끼우면 수집이 중간에
# 끊기고(진행 상태는 남지만) 그날 할당량만 날린다. FORCE_DEPLOY=true 로 건너뛸 수 있다.
wait_for_batch() {
  local waited=0 max=$(( ${BATCH_WAIT_MIN:-30} * 60 ))
  while $COMPOSE exec -T backend python -c "
import sys
from app.batch.lock import is_locked
sys.exit(0 if any(is_locked(n) for n in ('places_build', 'refresh_places')) else 1)
" >/dev/null 2>&1; do
    if [ "${FORCE_DEPLOY:-false}" = "true" ]; then
      echo "⚠ 배치 진행 중이지만 FORCE_DEPLOY=true 라 그대로 진행합니다." >&2
      return 0
    fi
    if [ "$waited" -ge "$max" ]; then
      echo "✗ 배치가 ${BATCH_WAIT_MIN:-30}분 넘게 돌고 있습니다." >&2
      echo "  끝난 뒤 다시 배포하거나, FORCE_DEPLOY=true ./deploy.sh 로 강행하세요." >&2
      exit 1
    fi
    [ "$waited" -eq 0 ] && echo "▶ 배치 진행 중 — 끝날 때까지 기다립니다(최대 ${BATCH_WAIT_MIN:-30}분)..."
    sleep 30
    waited=$(( waited + 30 ))
  done
}
wait_for_batch

# 이미지는 CI 가 구워 GHCR 에 올려 둔다. 여기서는 받아서 띄우기만 한다
# (1~2 OCPU VM 에서 Next.js 빌드는 수십 분이 걸리거나 메모리가 모자라 죽는다).
echo "▶ 이미지 받는 중 (태그: ${IMAGE_TAG:-latest})..."
$COMPOSE pull

# LOCALDATA CSV 를 담을 호스트 디렉터리를 **현재 사용자로** 먼저 만든다.
# 없으면 Docker 가 바인드 마운트 지점을 root 소유로 만들어 버리고,
# uid 1000 으로 도는 백엔드 컨테이너가 거기에 파일을 쓰지 못한다.
localdata_dir="${LOCALDATA_HOST_DIR:-./data/localdata}"
mkdir -p "$localdata_dir" || {
  echo "✗ $localdata_dir 를 만들지 못했습니다." >&2; exit 1; }
# 이 디렉터리에 쓰는 건 컨테이너(uid ${APP_UID:-1000})다 — 현재 사용자 기준으로 검사하면
# Oracle 우분투처럼 ubuntu=1001 인 환경에서 멀쩡한 디렉터리를 거절한다(실제로 그랬다).
app_uid="${APP_UID:-1000}"
owner_uid="$(stat -c %u "$localdata_dir")"
perm="$(stat -c %a "$localdata_dir")"
if [ "$owner_uid" != "$app_uid" ] && [ "${perm: -1}" != "7" ] && [ "${perm: -1}" != "3" ]; then
  echo "✗ 컨테이너(uid $app_uid)가 $localdata_dir 에 쓸 수 없습니다(소유자 uid $owner_uid, 권한 $perm)." >&2
  echo "  sudo chown -R $app_uid:$app_uid $localdata_dir   # 또는  sudo chmod -R a+rwX $localdata_dir" >&2
  exit 1
fi

echo "▶ 기동 (${DOMAIN})..."
$COMPOSE up -d --remove-orphans

echo "▶ 백엔드 헬스체크 대기..."
healthy=false
for i in $(seq 1 45); do
  if $COMPOSE exec -T backend python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    healthy=true
    break
  fi
  sleep 2
done
if [ "$healthy" != true ]; then
  echo "✗ 백엔드 헬스체크 실패 — 이전 버전이 아직 떠 있을 수 있습니다" >&2
  $COMPOSE logs --tail=50 backend >&2
  exit 1
fi
echo "✓ 백엔드 정상"

# 교체되고 남은 이전 이미지는 지운다(100GB 디스크가 조용히 차는 것을 막는다).
# 실행 중인 컨테이너가 쓰는 이미지는 대상이 아니다.
echo "▶ 이전 이미지 정리..."
docker image prune -f >/dev/null 2>&1 || true


# 크론(배치·백업·디스크 점검) 설치. 이미 있으면 갱신한다.
if [ "${INSTALL_CRON:-true}" = "true" ]; then
  echo "▶ 운영 크론 설치..."
  ./scripts/ops/install_cron.sh || echo "  (크론 설치 실패 — 나중에 ./scripts/ops/install_cron.sh 로 다시)" >&2
fi

echo "✓ 배포 완료"
echo "   프론트:  https://${DOMAIN}"
echo "   API:     https://api.${DOMAIN}/health"
echo "   (최초 접속 시 Caddy 가 HTTPS 인증서를 자동 발급합니다. 수십 초 소요될 수 있음)"
