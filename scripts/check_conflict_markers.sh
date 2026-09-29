#!/usr/bin/env bash
# 병합 충돌 마커가 커밋됐는지 검사한다.
# 문서·설정 파일의 마커는 테스트가 잡아 주지 않아 그대로 머지된 적이 있다.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# 이 스크립트 자신과 락파일·빌드 산출물은 제외한다.
hits=$(git grep -nE '^(<{7}|={7}|>{7})( |$)' -- \
  '*.md' '*.yml' '*.yaml' '*.json' '*.toml' '*.ini' '*.txt' '*.sh' '*.env*' 'Dockerfile*' \
  ':(exclude)scripts/check_conflict_markers.sh' \
  ':(exclude)**/pnpm-lock.yaml' 2>/dev/null)

if [ -n "$hits" ]; then
  echo "✗ 충돌 마커가 남아 있습니다:" >&2
  echo "$hits" >&2
  exit 1
fi
echo "✓ 충돌 마커 없음"
