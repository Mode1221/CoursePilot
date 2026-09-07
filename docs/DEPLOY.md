# 배포 가이드

CoursePilot는 키 없이도 Mock/폴백으로 완전히 동작한다. 실서비스 배포 시 아래 환경변수를 채운다.

## 구성 요소
- **frontend** (Next.js) — 포트 3000
- **backend** (FastAPI + Socket.IO) — 포트 8000
- **db** (PostgreSQL + pgvector) — 포트 5432

## 환경변수

### Backend (`backend/.env`)
| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `DATABASE_URL` | 권장 | `postgresql+psycopg://coursepilot:coursepilot@localhost:5432/coursepilot` | 미설정/연결 실패 시 인메모리 폴백(영속성 없음) |
| `OPENAI_API_KEY` | 선택 | `""` | 없으면 규칙 기반 파싱 + 해시 임베딩 폴백 |
| `OPENAI_MODEL` | 선택 | `gpt-4o-mini` | 챗/요약 모델 |
| `MAP_PROVIDER` | 선택 | `naver` | 지도/장소 어댑터 벤더 |
| `NAVER_CLIENT_ID` | 선택 | `""` | 없으면 Mock 지도로 폴백 |
| `NAVER_CLIENT_SECRET` | 선택 | `""` | |
| `CORS_ORIGINS` | 권장 | `["http://localhost:3000"]` | 프론트 도메인(JSON 배열) |

### Frontend (`frontend/.env.local`)
| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE` | 권장 | `http://localhost:8000` | 백엔드 + Socket.IO 주소 |

> 키 발급: 지도(Naver Cloud Platform → Maps, 카드 등록 필요·소규모는 무료 한도), OpenAI(platform.openai.com).
> 키는 배포 직전에 주입하는 것을 권장(개발 중엔 폴백으로 충분).

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
