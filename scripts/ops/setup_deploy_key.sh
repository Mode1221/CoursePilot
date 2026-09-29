#!/usr/bin/env bash
# GitHub Actions → VM 즉시 배포용 SSH 키를 만든다(VM 에서 한 번 실행).
#
#   ./scripts/ops/setup_deploy_key.sh
#
# 1) 배포 전용 키를 만들고 authorized_keys 에 "배포 스크립트만 실행" 제한을 붙여 등록한다.
# 2) GitHub 저장소 Secrets 에 넣을 값 4개를 출력한다.
# 다시 실행해도 안전하다(키가 있으면 재사용, 등록 줄은 한 번만).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
ROOT="$(pwd)"
KEY="$HOME/.ssh/coursepilot_deploy"
AUTH="$HOME/.ssh/authorized_keys"

mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
if [ ! -f "$KEY" ]; then
  ssh-keygen -q -t ed25519 -N "" -C "github-deploy" -f "$KEY"
fi
touch "$AUTH" && chmod 600 "$AUTH"
pub="$(cat "$KEY.pub")"
line="command=\"$ROOT/scripts/ops/deploy_hook.sh\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty,no-user-rc $pub"
if ! grep -qF "$pub" "$AUTH"; then
  echo "$line" >> "$AUTH"
fi

host="$(curl -fsS -4 --max-time 5 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
known="$(ssh-keyscan -t ed25519 localhost 2>/dev/null | sed "s/^localhost/$host/")"

cat <<OUT

GitHub → 저장소 → Settings → Secrets and variables → Actions → New repository secret 으로 4개를 넣으세요.
(값은 ===== 줄 사이 전부, 앞뒤 공백 없이)

[1] 이름: DEPLOY_HOST
=====
$host
=====

[2] 이름: DEPLOY_USER
=====
$(whoami)
=====

[3] 이름: DEPLOY_KNOWN_HOSTS
=====
$known
=====

[4] 이름: DEPLOY_SSH_KEY   (BEGIN 줄부터 END 줄까지 전부)
=====
$(cat "$KEY")
=====

이 키로는 배포 스크립트 하나만 실행된다(셸 접속 불가). 키를 바꾸려면 $KEY* 를 지우고
authorized_keys 에서 github-deploy 줄을 지운 뒤 다시 실행한다.
OUT
