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

## 서브에이전트 (`.claude/agents/`)
영역별 전담 에이전트. 작업이 한 영역에 들어가면 해당 에이전트에 맡기고, 여러 영역이면 나눠서 병렬로 맡긴다.
| 에이전트 | 영역 |
|---|---|
| `be-api` | 라우터·신원(체험/카카오/토큰)·사용 한도·액션 큐·실시간·QA 모드 |
| `be-pipeline` | 코스 생성·편집·합의(pipeline/), 답변·근거, 리뷰 태그, 품질 평가·계수 |
| `be-data` | 장소 어댑터·배치 수집/갱신·할당량, DB 모델·스키마, 학습 신호 저장 |
| `fe-web` | Next.js 화면·컴포넌트·상태·API/소켓/지도 서비스·디자인 토큰 |
| `ops` | CI·자동 머지·이미지·SSH 배포·크론·운영 스크립트·환경변수 |
| `qa` | 버그 재현·회귀 테스트·E2E·운영 QA(e2e-prod)·flaky 조사 |
- 스키마 변경(be-data)과 API 계약 변경(be-api ↔ fe-web)처럼 경계를 넘는 작업은 순서를 정해 맡긴다.
- 에이전트 파일도 코드와 같이 관리한다 — 모듈·규칙이 바뀌면 해당 에이전트 파일도 같은 PR 에서 고친다.

## Claude 설정
- `.claude/settings.json`: 읽을 필요 없는 경로(node_modules, .next, __pycache__, 락파일, 캐시 등)를 `permissions.deny` 의 Read 규칙으로 차단.
  Claude Code 는 `.claudeignore` 를 읽지 않으므로 제외 목록은 이 파일에서 관리한다.

## 인수인계 문서
- `docs/STATUS.md` 기능·개발 단계 / `docs/ARCHITECTURE.md` 모듈·요청흐름 / `docs/BACKLOG.md` 남은 과제·착수점.
- **문서 갱신은 그 변경과 같은 PR 에 포함한다**(나중에 몰아서 하지 않는다).
  - 기능 추가/변경 → `STATUS.md`, 모듈·흐름 변경 → `ARCHITECTURE.md`, 과제 상태 변화 → `BACKLOG.md`.
  - `STATUS.md` 머리말의 "최종 갱신" 줄은 **날짜만** 올린다. PR 번호는 적지 않는다
    (모든 PR 이 같은 줄을 고쳐 열린 PR 끼리 매번 충돌했다 — 반영 범위는 git log 로 본다).
  - 문서를 건드리지 않은 PR 은 **PR 설명에 "문서 변경 불필요" 와 그 이유를 한 줄** 남긴다
    (예: 내부 리팩터링으로 동작·모듈 경계 변화 없음).
