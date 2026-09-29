# CoursePilot

서비스명은 **픽앤어스(PickNuS)**(2026-09-29 변경 — "CoursePilot" 은 제9류 등록상표가 있어 바꿨다).
화면·메타·약관·SMS 등 사용자에게 보이는 이름은 픽앤어스로 쓴다. 저장소·이미지·DB·도메인·localStorage 키·크론 표식 같은
내부 식별자(`coursepilot`)는 바꾸지 않는다(바꾸면 배포·데이터·로그인이 깨진다).

## 스택
Next.js+TS+Zustand / FastAPI+PostgreSQL+pgvector / Socket.IO / Claude Haiku(LLM, 없으면 규칙 폴백)

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

## 개발 워크플로 (푸시 = 배포)
- 브랜치: `main`에서 `claude/<주제>` 파고 작업. main 에 직접 push 하지 않는다.
- **`claude/*` 브랜치는 push 하면 끝까지 자동**: CI → PR 자동 생성·squash 머지(`auto-merge.yml`, 브랜치가 최신 main 을
  품을 때만) → arm64 이미지 빌드 → SSH 배포(`release.yml`) → 운영 QA(`qa.yml`). 10~15분.
  - 그래서 **미완성·검증 전 작업은 `wip/<주제>` 로 push** 한다(CI 만 돌고 머지·배포 안 됨). 끝나면 `claude/` 로 올린다.
  - main 이 앞서 있으면 자동 머지가 멈추고 PR 에 댓글이 달린다 → `git rebase origin/main` 후 다시 push.
  - 자동 머지 끄기: 저장소 Variables `AUTO_MERGE=false`. 배포 끄기: VM `.env` `AUTO_DEPLOY=false`.
- push 전 검증(로컬): `./scripts/check.sh` (백엔드 pytest·ruff → 프론트 tsc·eslint·vitest·build). E2E까지: `./scripts/check.sh --e2e`.
  - 파일을 추가한 뒤에도 반드시 다시 실행할 것(새 테스트 파일의 lint 위반이 CI에서만 잡히는 경우가 있음).
- 외부연동은 키 없으면 폴백 유지(테스트는 키 없는 환경 기준).
- 문서에 없는 절차가 생기면 그 PR 에서 문서로 남긴다 — **특정 대화 세션의 기억에 의존하지 않는다.**

## 새 세션에서 이어받기
어느 세션(로컬 Claude Code, 원격 세션, 예약 작업)이든 이 절만 보고 이어서 일할 수 있어야 한다.
1. 현황: `docs/STATUS.md`(무엇이 되는지) → `docs/BACKLOG.md`(다음 할 일) → `git log --oneline -20 origin/main`(최근 변경).
2. push 권한: 세션이 연결된 GitHub 계정이 저장소(Mode1221/CoursePilot)에 쓰기 권한이 없으면, 그 환경의 git 인증
   (로컬 PC 의 git 자격 증명, 또는 환경변수 `GH_TOKEN` 에 넣은 fine-grained PAT: Contents·Pull requests·Workflows 쓰기)을 쓴다.
   **토큰을 채팅에 붙여 넣거나 로그·커밋에 출력하지 않는다.**
3. 배포 확인(토큰 없이 가능 — 공개 저장소):
   - 머지: `git ls-remote origin refs/heads/main` / 브랜치가 사라졌는지.
   - 워크플로: https://github.com/Mode1221/CoursePilot/actions (CI · Auto merge · Release images · Production QA).
   - 운영 QA 실패는 `qa-failure` 라벨 이슈로 열린다(통과하면 자동으로 닫힘).
4. 운영 서버(Oracle ARM VM, `/opt/coursepilot`): 접속은 저장소 주인의 SSH 로만. 배포는 자동이며
   수동이 필요하면 `./scripts/ops/auto_deploy.sh` (VM 은 detached HEAD — `git pull` 쓰지 않는다). 절차는 `docs/DEPLOY.md`.
5. 비밀값 위치: GitHub Secrets(`DEPLOY_*`, `QA_TOKEN`, 선택 `ALERT_WEBHOOK_URL`), VM `.env`(API 키·`SESSION_SECRET`·`ADMIN_TOKEN`·`QA_TOKEN`).
   값은 문서·채팅에 적지 않는다.
6. 자동으로 도는 것(다시 실행하지 말 것 — 요금·한도가 이중으로 든다): 운영 QA 3시간마다(Actions),
   장소 수집·갱신·팝업·품질 점검·백업·정리(VM 크론, 시각표는 `docs/DEPLOY.md` "장소 데이터 배치").
   감시가 필요하면 결과(Actions 페이지, VM `logs/*.log`)만 읽는다.

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
