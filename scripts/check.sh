#!/usr/bin/env bash
# 푸시 전 로컬 검증 일괄 실행. CI(backend/frontend/e2e)와 같은 검사를 같은 순서로 돌린다.
#   ./scripts/check.sh        # 단위 검사(빠름)
#   ./scripts/check.sh --e2e  # Playwright E2E 까지
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_e2e=false
[[ "${1:-}" == "--e2e" ]] && run_e2e=true

echo "▶ backend: pytest"
(cd "$root/backend" && python -m pytest -q)

echo "▶ backend: ruff"
(cd "$root/backend" && ruff check app tests)

echo "▶ frontend: tsc"
(cd "$root/frontend" && npx tsc --noEmit)

echo "▶ frontend: eslint"
(cd "$root/frontend" && npx eslint src --max-warnings 0)

echo "▶ frontend: vitest"
(cd "$root/frontend" && npx vitest run)

echo "▶ frontend: build"
(cd "$root/frontend" && pnpm build >/dev/null)

if $run_e2e; then
  echo "▶ e2e: playwright"
  (cd "$root/frontend" && npx playwright test)
fi

echo "✅ 모든 검사 통과"
