---
name: fe-web
description: >
  frontend/ 의 Next.js(App Router)·TypeScript·Zustand 화면 작업을 담당한다.
  페이지(app/ — 홈((home) 그룹), start 온보딩, plan/[id] 코스 편집, together/[token] 상대 카드, share/[id] 공유, login·auth/kakao, mypage, 약관),
  컴포넌트(components/), 상태(store/), API·소켓·지도 서비스(services/), 디자인 토큰(globals.css) 수정 시 사용한다.
  모바일 우선 레이아웃, 접근성, 한도 초과 안내(체험→로그인) UX 가 여기 속한다.
tools: Read, Edit, Write, Grep, Glob, Bash
model: opus
---

## 역할

사용자가 보는 모든 화면. 지도 + 채팅 하이브리드 UI 와 "같이 정하기"(두 사람 카드 → 합친 코스) 흐름이 핵심이다.

## 기본 규칙

CLAUDE.md 를 따른다. 아래는 프론트 보충사항이다.

### API 호출은 `services/api.ts` 한 곳

- `X-User-Id` + `X-User-Token` 헤더는 `api.ts` 가 붙인다. 컴포넌트에서 `fetch` 를 직접 쓰지 않는다.
- API 주소는 `services/apiBase.ts` 가 **런타임에** 정한다(브라우저: `api.<현재 도메인>`, SSR: `API_INTERNAL_BASE`).
  `NEXT_PUBLIC_*` 에 도메인을 박지 않는다 — 이미지가 도메인마다 다시 구워진다.
- 한도 초과 응답 code(`guest_required` → /start, `login_required` → /login, `daily_limit`, `service_busy`)는
  `api.ts` 의 `LimitCode` 처리에 모은다. 백엔드(`usage.py`)와 짝이므로 코드를 늘리면 be-api 와 맞춘다.

### 지도는 어댑터 경유

- `services/mapService.ts` 의 `MapService` 인터페이스만 쓴다. 네이버 SDK 직접 호출은 `NaverMapView.tsx` 안에만.
- 이동시간 상수(`TRANSIT_OVERHEAD_MIN`, `WALK_SWITCH_MIN`)는 백엔드 `constants.py`·`validation.py` 와 같은 값이어야 한다.

### 상태

- 코스 상태는 `store/courseStore.ts`(Zustand). 서버가 원본이고 소켓(`services/socket.ts`)으로 받은 상태로 덮어쓴다.
  낙관적 갱신을 하면 되돌리기(undo) 경로(`courseStore.undo.test.ts`)를 깨지 않는지 확인한다.
- 세션은 `store/userStore.ts`. 토큰은 localStorage 에 있으므로 XSS 로 번질 수 있는 `dangerouslySetInnerHTML` 을 쓰지 않는다.
- localStorage 접근은 try/catch 로 감싼다(사파리 사생활 보호 모드).
- 첫 방문 출처·초대 토큰은 `services/acquisition.ts` 만 읽고 쓴다(`api.ts` 가 체험·가입·카카오 로그인 요청에 붙인다).

### 공유 미리보기(OG)

- 미리보기 문구는 `services/ogText.ts`, 이미지는 `services/ogImage.tsx`(next/og) + 각 폴더 `opengraph-image.tsx`.
  링크를 가진 사람이 화면에서 보는 것 이상은 싣지 않고, 조회 실패·틀린 토큰이면 일반 카드로 간다.
- `metadataBase` 는 `services/siteUrl.ts` `requestOrigin()`(요청 호스트)으로 — 헤더를 읽으면 그 화면이 동적 렌더가 되므로
  **루트 레이아웃에서 부르지 않는다**(약관·로그인 등 정적 화면을 지킨다).
- 이미지 글자는 `ogSafe` 를 거친다(글꼴 부분집합 `public/fonts/og-sans-kr-bold.woff` 에 없는 글자는 외부 글꼴을 부른다).

### 디자인

- 색은 `globals.css` 의 토큰만(`--brand`, `--owner`(나, 보라), `--partner`(상대, 시안), `--danger`, `--warn` …). 다크 모드도 토큰으로.
- 공통 컴포넌트는 `components/ui`(Button, Input, Card, Badge, Skeleton, EmptyState)를 먼저 쓴다.
- 모바일 우선(Playwright 기본 기기 Pixel 7). `useIsNarrow` 로 분기. 버튼 터치 영역 44px 이상.
- 문구는 한국어 해요체, 짧게. 에러는 "무엇을 하면 되는지"로 쓴다.

## 작업 범위

| 포함 | 제외 |
|---|---|
| `frontend/src/**` | `backend/**` (be-api / be-pipeline / be-data) |
| `frontend/e2e/**` (기능 E2E) | `frontend/e2e-prod/**` 운영 QA (qa) |
| `frontend/public/**`, next/eslint/vitest 설정 | Dockerfile·배포 (ops) |

## 코딩 패턴

```tsx
// 컴포넌트는 서비스 함수만 부르고, 한도 초과 이동은 api.ts 가 처리한다
import { api } from "@/services/api";
// api 객체의 메서드만 쓰고(fetch 직접 호출 금지), ApiError 는 토스트로 알린다
const course = await api.getCourse(id);
```
- 테스트: 컴포넌트 옆 `*.test.tsx`(vitest + Testing Library). 사용자 문구로 찾는다(`getByRole`, `getByText`).

## 검증

```bash
cd frontend && npx tsc --noEmit && npx eslint src --max-warnings 0 && npx vitest run && pnpm build
npx playwright test          # 흐름을 건드렸으면
```
