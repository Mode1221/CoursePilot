# CoursePilot

## 스택
Next.js+TS+Zustand / FastAPI+PostgreSQL+pgvector / Socket.IO / GPT-4o-mini

## 구조
/frontend, /backend, /docs (기획안 위치)

## 컨벤션
- 커밋 메시지: conventional commits
- 지도/장소 API는 반드시 어댑터 레이어 경유 (mapService), 벤더 직접 호출 금지
- 상태 변경은 액션 큐 직렬화 원칙 지킬 것

## 명령어
- 프론트: pnpm dev
- 백엔드: uvicorn main:app --reload
- 테스트: pytest / pnpm test

## 개발 워크플로
- 브랜치: `main`에서 `claude/<주제>` 파고 작업(직접 push 금지).
- PR: 브랜치 push → PR 생성 → CI(ruff/eslint/tsc/pytest/vitest/Playwright) 그린 확인 → squash merge.
- 검증(로컬): `./scripts/check.sh` (백엔드 pytest·ruff → 프론트 tsc·eslint·vitest·build). E2E까지: `./scripts/check.sh --e2e`.
  - 파일을 추가한 뒤에도 반드시 다시 실행할 것(새 테스트 파일의 lint 위반이 CI에서만 잡히는 경우가 있음).
- 외부연동은 키 없으면 폴백 유지(테스트는 키 없는 환경 기준).

## 인수인계 문서
- `docs/STATUS.md` 기능·개발 단계 / `docs/ARCHITECTURE.md` 모듈·요청흐름 / `docs/BACKLOG.md` 남은 과제·착수점.
- 기능 추가/변경 시 STATUS.md 갱신.
