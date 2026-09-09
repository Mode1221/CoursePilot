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
| `OPENAI_API_KEY` / `OPENAI_MODEL` | 선택 | `""` / `gpt-4o-mini` | `LLM_PROVIDER=openai`일 때, 그리고 리뷰 임베딩(pgvector 의미 검색)에 필요. 없으면 해시 폴백이라 의미 검색 품질이 없음 |
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

## 호스팅 추천 (소규모 베타)
비용·효율 기준. 단일 VM 1대면 앱+DB가 한 번에 뜬다(별도 관리형 DB 불필요).
- **Oracle Cloud 프리티어 (ARM Ampere, 춘천)** — 평생 무료(4 vCPU/24GB), 한국 리전. 베타 최적. (1순위)
- **AWS Lightsail 서울 ($5~12/월)** — 고정가·가장 단순. 무료가 부담되면 이쪽. (대안)
- 스택은 멀티아치라 ARM/x86 모두 동작.

## 프로덕션 배포 (단일 VM, 원커맨드) — 권장
자동 HTTPS(Caddy) + 리버스 프록시 + WebSocket + pgvector 컨테이너 포함.

**사전 준비**
1. VM 생성(Ubuntu 22.04+), Docker + Compose v2 설치.
2. 도메인 DNS A 레코드: `example.com` 과 `api.example.com` → VM 공인 IP.
3. 방화벽/보안그룹에서 **80, 443** 인바운드 오픈.

**배포**
```bash
git clone <repo> && cd CoursePilot
cp .env.prod.example .env      # DOMAIN, POSTGRES_PASSWORD + 보유 키 채우기
./deploy.sh                    # 빌드·기동·헬스체크까지 한 번에
```
- `docker-compose.prod.yml` 가 db/backend/frontend/caddy 를 기동.
- Caddy 가 최초 접속 시 Let's Encrypt 인증서 자동 발급 → `https://example.com`, `https://api.example.com`.
- `NEXT_PUBLIC_*` 는 빌드 시 주입되므로 지도 클라이언트 ID·API 주소 변경 시 프론트 재빌드(`./deploy.sh` 재실행).

### 개발용 Docker Compose
```bash
docker compose up --build -d   # docker-compose.yml (로컬, HTTPS/프록시 없음)
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

## 장소 데이터 배치 (크론)
장소 DB 는 검색 API 로 즉석에서 만드는 대신 배치로 쌓고 주기적으로 갱신한다.
유료 콜은 무료 한도 안에서 페이싱되며, 한도를 넘기면 호출 자체가 차단된다(`app/quota.py`).

```cron
# 폐업 대장(LOCALDATA) 내려받기 — 주 1회
0 3 * * 1 cd /srv/coursepilot/backend && python scripts/fetch_localdata.py

# 상권 수집·보강 — 매일(영업시간 160건/일, 평점 11건/일로 나눠 채운다)
0 4 * * * cd /srv/coursepilot/backend && python scripts/build_places.py

# 저장된 장소 갱신 — 매일(폐업 전체 / 영업시간 30일 / 평점 90일 TTL)
30 4 * * * cd /srv/coursepilot/backend && python scripts/refresh_places.py
```

- 실행이 겹치면 뒤에 뜬 쪽이 종료 코드 1 로 빠진다(`batch_lock`). 크론 중복은 걱정하지 않아도 된다.
- 초기 구축은 며칠 걸린다 — 영업시간·평점을 하루 할당량씩 채우는 것이 설계 전제다.
- 사용량은 `GET /admin/metrics` 의 `quotas` 로 확인하고, 80%·소진 시점에는 `ALERT_WEBHOOK_URL` 로 알림이 간다.

### 키 주의
- Google Cloud 콘솔에서 **키 제한(IP/HTTP 리퍼러)과 일일 할당량 상한**을 반드시 설정한다. 코드 쪽 한도는 인스턴스 기준이라 최후 방어선이 아니다.
- 네이버 경로는 NCP 전용 키(`NCP_API_KEY_ID/KEY`)를 쓴다. 개발자센터 키(`NAVER_CLIENT_ID/SECRET`)는 지역·블로그 검색용이다.
