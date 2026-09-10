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

## Claude 설정
- `.claude/settings.json`: 읽을 필요 없는 경로(node_modules, .next, __pycache__, 락파일, 캐시 등)를 `permissions.deny` 의 Read 규칙으로 차단.
  Claude Code 는 `.claudeignore` 를 읽지 않으므로 제외 목록은 이 파일에서 관리한다.

## 인수인계 문서
- `docs/STATUS.md` 기능·개발 단계 / `docs/ARCHITECTURE.md` 모듈·요청흐름 / `docs/BACKLOG.md` 남은 과제·착수점.
- **문서 갱신은 그 변경과 같은 PR 에 포함한다**(나중에 몰아서 하지 않는다).
  - 기능 추가/변경 → `STATUS.md`, 모듈·흐름 변경 → `ARCHITECTURE.md`, 과제 상태 변화 → `BACKLOG.md`.
  - `STATUS.md` 머리말의 "최종 갱신: … (PR #N까지 반영)" 을 그 PR 번호로 올린다.
  - 문서를 건드리지 않은 PR 은 **PR 설명에 "문서 변경 불필요" 와 그 이유를 한 줄** 남긴다
    (예: 내부 리팩터링으로 동작·모듈 경계 변화 없음).
