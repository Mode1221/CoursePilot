# 배포 가이드

CoursePilot는 키 없이도 Mock/폴백으로 완전히 동작한다. 실서비스 배포 시 아래 환경변수를 채운다.

## 구성 요소
- **frontend** (Next.js) — 포트 3000
- **backend** (FastAPI + Socket.IO) — 포트 8000
- **db** (PostgreSQL + pgvector) — 포트 5432

## 환경변수

모든 외부 연동은 **키가 있으면 실연동, 없으면 폴백**으로 동작한다. "키만 채우면 실서비스"가 되도록 설계됨.

### Backend (`backend/.env`) — `backend/.env.example` 참고
| 변수 | 필수 | 기본값 | 없을 때 동작 |
|---|---|---|---|
| `DATABASE_URL` | 권장 | `postgresql+psycopg://…/coursepilot` | 인메모리 폴백(영속성 없음) |
| `LLM_PROVIDER` | 선택 | `anthropic` | `anthropic`\|`openai` |
| `ANTHROPIC_API_KEY` | 선택 | `""` | 규칙 기반 파서로 폴백 |
| `ANTHROPIC_MODEL` | 선택 | `claude-haiku-4-5` | 조건 분해 모델 |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | 선택 | `""` / `gpt-4o-mini` | `LLM_PROVIDER=openai`일 때만 |
| `MAP_PROVIDER` | 선택 | `naver` | 지도/장소 어댑터 벤더 |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 선택 | `""` | Mock 장소로 폴백 |
| `GOOGLE_MAPS_API_KEY` | 선택 | `""` | 장소 평점 보강 생략(평점 None) |
| `NHN_SMS_APP_KEY` / `NHN_SMS_SECRET_KEY` / `NHN_SMS_SENDER` | 선택 | `""` | SMS 인증 생략(가입 시 인증 불요, dev 코드 응답 노출) |
| `PORTONE_API_KEY` / `PORTONE_API_SECRET` | 선택 | `""` | 결제 검증 생략(포인트 즉시 지급) |
| `POINT_PRICE_KRW` | 선택 | `1000` | 포인트 1개당 결제금액(검증용) |
| `CORS_ORIGINS` | 권장 | `["http://localhost:3000"]` | 프론트 도메인(JSON 배열) |

### Frontend (`frontend/.env.local`)
| 변수 | 필수 | 기본값 | 없을 때 동작 |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE` | 권장 | `http://localhost:8000` | 백엔드 + Socket.IO 주소 |
| `NEXT_PUBLIC_NAVER_MAP_CLIENT_ID` | 선택 | `""` | SVG 지도로 폴백 |

### 키 발급처
- **LLM**: Anthropic(console.anthropic.com) — `ANTHROPIC_API_KEY`. (대안: OpenAI)
- **지도 렌더/장소/길찾기**: 네이버 클라우드 플랫폼 → Maps + 지역검색(Application 등록). 지도 렌더용 `NEXT_PUBLIC_NAVER_MAP_CLIENT_ID`는 서비스 URL 등록 필요.
- **평점**: Google Cloud → Places API(`GOOGLE_MAPS_API_KEY`). 요약 아님·숫자만(약관 안전), attribution 준수.
- **SMS**: NHN Cloud → SMS(발신번호 사전 등록).
- **결제**: 포트원(아임포트) → v1 REST API 키/시크릿.

> 키는 배포 직전 주입 권장(개발 중엔 폴백으로 충분). 시크릿은 소스에 커밋하지 말 것(`.env`는 gitignore).

## 배포 방법

### Docker Compose (권장)
```bash
docker compose up --build -d
```
- `db`는 pgvector 이미지, healthcheck 통과 후 `backend` 기동.
- 키는 `backend` 서비스 `environment` 또는 `.env`로 주입.

### 개별 배포
```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
# frontend
cd frontend && pnpm install && pnpm build && pnpm start
```

## DB 초기화
백엔드 startup에서 `CREATE EXTENSION IF NOT EXISTS vector` + 테이블 자동 생성(`init_db`).
성공 시 영속 모드, 실패 시 인메모리 폴백으로 자동 전환된다(전 스토어 `db.is_ready()` 참조).

## 헬스체크 / 스모크
```bash
curl http://localhost:8000/health          # {"status":"ok"}
curl -X POST http://localhost:8000/courses # 코스 생성
```

## 운영 주의
- Socket.IO는 WebSocket 사용 — 리버스 프록시(Nginx 등)에서 `Upgrade` 헤더 전달 필요.
- 다중 백엔드 인스턴스로 확장 시 Socket.IO는 메시지 브로커(예: Redis) 어댑터가 필요(현재 단일 프로세스 기준).
- 크레딧 원자적 차감은 DB 행 잠금(`FOR UPDATE`)에 의존 — 인메모리 폴백은 단일 프로세스에서만 정확.
