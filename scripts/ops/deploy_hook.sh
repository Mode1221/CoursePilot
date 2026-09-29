#!/usr/bin/env bash
# GitHub Actions 가 SSH 로 부르는 배포 입구. authorized_keys 의 command= 로 이 스크립트만 실행된다.
#
#   command="<저장소>/scripts/ops/deploy_hook.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty,no-user-rc ssh-ed25519 AAAA… github-deploy
#
# 받는 입력은 SSH_ORIGINAL_COMMAND 의 "deploy <40자 sha>" 하나뿐이다. 그 외엔 거절한다.
# 실제 배포는 auto_deploy.sh 가 한다(origin/main 을 받아 sha 이미지로 배포, 실패하면 되돌림, 락으로 겹침 방지).
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

cmd="${SSH_ORIGINAL_COMMAND:-}"
if ! [[ "$cmd" =~ ^deploy\ ([0-9a-f]{40})$ ]]; then
  echo "✗ 허용되지 않은 명령" >&2
  exit 2
fi
sha="${BASH_REMATCH[1]}"
echo "▶ GitHub 에서 배포 요청: ${sha:0:7}"
# 그 사이 main 이 더 나아갔으면 auto_deploy 는 최신 main 을 배포한다(뒤 커밋의 워크플로도 곧 온다)
exec ./scripts/ops/auto_deploy.sh --wait
