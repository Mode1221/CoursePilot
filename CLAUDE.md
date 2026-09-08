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
- 검증(로컬): 백엔드 `cd backend && python -m pytest -q && ruff check .`, 프론트 `cd frontend && npx tsc --noEmit && npx eslint src --max-warnings 0 && pnpm test`.
- 외부연동은 키 없으면 폴백 유지(테스트는 키 없는 환경 기준).

## 인수인계 문서
- `docs/STATUS.md` 기능·개발 단계 / `docs/ARCHITECTURE.md` 모듈·요청흐름 / `docs/BACKLOG.md` 남은 과제·착수점.
- 기능 추가/변경 시 STATUS.md 갱신.
