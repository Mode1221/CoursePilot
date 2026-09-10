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

## 이미지는 CI 가 굽고, VM 은 받아서 띄운다
1~2 OCPU arm64 VM 에서 Next.js 를 빌드하면 수십 분이 걸리거나 메모리가 모자라 죽는다.
그래서 `main` 에 머지되면 GitHub Actions(`.github/workflows/release.yml`)가 buildx +
QEMU 로 **linux/arm64** 이미지를 만들어 GHCR 에 올린다.

```
ghcr.io/mode1221/coursepilot-backend:{커밋sha, latest}
ghcr.io/mode1221/coursepilot-frontend:{커밋sha, latest}
```

`docker-compose.prod.yml` 은 `build:` 대신 `image:` 로 이 이미지를 참조한다.
`.env` 의 `IMAGE_TAG` 로 버전을 고른다(기본 `latest`, 커밋 sha 로 고정 가능).
`deploy.sh` 는 **pull → up -d → 헬스체크 대기 → 이전 이미지 정리** 순으로 돈다.

**GHCR 이 비공개라면** VM 에서 한 번 로그인해 둔다(`read:packages` 권한 PAT):
```bash
echo <PAT> | docker login ghcr.io -u <github-id> --password-stdin
```
아니면 GitHub 패키지 설정에서 public 으로 바꾼다. `deploy.sh` 가 기동 전에
이미지를 볼 수 있는지 확인하고, 못 보면 이 안내를 띄우고 멈춘다.

### 도메인을 이미지에 박지 않는다
`NEXT_PUBLIC_*` 는 빌드 시점에 번들에 박힌다. 도메인을 빌드 인자로 받으면 도메인이
바뀔 때마다 이미지를 다시 구워야 한다. 그래서 브라우저는 현재 호스트에서
`api.<도메인>` 을 유도하고(`frontend/src/services/apiBase.ts`), SSR 만 런타임
환경변수 `API_INTERNAL_BASE`(compose 가 `http://backend:8000` 으로 준다)를 읽는다.
지도 SDK 키(`NEXT_PUBLIC_NAVER_MAP_CLIENT_ID`)는 빌드 시점 값이라 GitHub 저장소
변수(Variables)에 넣는다 — 바꾸면 이미지를 다시 구워야 한다.

## 대상 서버 (Oracle Cloud Ampere / arm64)
Oracle Cloud 오사카 리전 Ampere A1(aarch64) + Ubuntu 24.04 를 기준으로 맞춰 두었다.
compose 가 쓰는 이미지는 모두 `linux/arm64` 빌드가 있는 태그로 고정돼 있다.

| 서비스 | 이미지(고정 태그) | arm64 |
|---|---|---|
| db | `pgvector/pgvector:0.8.0-pg16` | ✅ |
| redis(선택) | `redis:7.4.1-alpine` | ✅ |
| caddy | `caddy:2.8.4` | ✅ |
| backend(빌드) | `python:3.11.13-slim-bookworm` | ✅ |
| frontend(빌드) | `node:20.18.1-slim` | ✅ |

`deploy.sh` 는 아키텍처 특정 명령을 쓰지 않는다(bash + docker compose v2 + coreutils).
기동 시 `uname -m` 과 배포판을 찍어 주므로 로그로 확인할 수 있다.

## DB 접근은 Tailscale 사설망으로만
`5432` 는 공개 IP 에 열지 않는다. compose 의 포트 매핑이
`"${TAILSCALE_IP:-127.0.0.1}:5432:5432"` 라서, `.env` 의 `TAILSCALE_IP` 에
`tailscale ip -4` 값을 넣으면 그 인터페이스에만 바인딩된다. 값을 비우면
루프백으로 떨어진다 — **어느 쪽이든 외부에서 닿지 않는다.**
`deploy.sh` 는 기동 전에 그 IP 가 실제로 이 서버에 붙어 있는지 확인하고,
아니면 멈춘다(틀린 값으로 컨테이너가 바인딩 실패하는 것을 막는다).
클라우드 보안 그룹에서도 5432 는 열지 말 것(80/443 만 연다).

## DB 초기화
백엔드 startup에서 `CREATE EXTENSION IF NOT EXISTS vector` + 테이블 자동 생성(`init_db`).
성공 시 영속 모드, 실패 시 인메모리 폴백으로 자동 전환된다(전 스토어 `db.is_ready()` 참조).

## 헬스체크 / 스모크
```bash
curl http://localhost:8000/health          # liveness: {"status":"ok"}
curl http://localhost:8000/health/ready    # readiness: db·env·비어 있는 필수 설정
curl -X POST http://localhost:8000/courses # 코스 생성
```
`ENV=production` 이면 `/health/ready` 는 DB 미연결이거나 `SESSION_SECRET`/`ADMIN_TOKEN`
이 비어 있을 때 **503** 을 낸다. 로드밸런서·오케스트레이터의 readiness probe 는
`/health` 가 아니라 `/health/ready` 를 봐야 미완성 인스턴스로 트래픽이 가지 않는다.

## 다중 인스턴스로 늘리기
`REDIS_URL` 을 채우고 redis 서비스를 함께 띄우면 Socket.IO 브로드캐스트가 인스턴스 간에 전달된다.
```bash
# .env: REDIS_URL=redis://redis:6379/0
docker compose --profile scale up -d            # redis 포함 기동
docker compose --profile scale up -d --scale backend=2
```
프로필을 쓰지 않으면 redis 는 뜨지 않고 단일 프로세스로 동작한다(기본값).
크레딧 차감은 DB 행 잠금에 의존하므로 다중 인스턴스에서는 DB 영속이 필수다.

## 키가 들어올 때마다: 외부 연동 스모크
키를 하나 넣을 때마다 그 벤더만 바로 확인한다. 실키로 1~2건만 부르고,
응답 필드명·타입이 코드가 기대하는 것과 같은지 대조해 PASS/FAIL 을 낸다.
```bash
cd backend
python scripts/smoke_kakao.py      # 카카오 로컬(키워드·카테고리 검색)
python scripts/smoke_naver.py      # 지역검색 + NCP 차량 경로
python scripts/smoke_tourapi.py    # TourAPI 검색 + 소개정보
python scripts/smoke_kopis.py      # KOPIS 공연 목록(XML)
python scripts/smoke_localdata.py  # LOCALDATA CSV 컬럼
python scripts/smoke_google.py     # Google Places(유료 — quota 차감·기록 확인)
python scripts/smoke_all.py        # 전부 한 번에(요약 표)
```
- 키가 없는 벤더는 **SKIP** 이고 종료 코드 0 — 아직 발급 전이어도 그냥 돌리면 된다.
- 불일치가 있으면 어느 필드가 어떤 타입으로 왔는지 찍는다.
- `smoke_google.py` 는 어댑터를 그대로 타므로 `quota.py` 무료 한도에 카운트되고,
  필드마스크가 티어별로 분리돼 있는지(과금 티어 상승 방지)도 함께 본다.

## 키 없이 전체 흐름 확인 (시드 데이터)
키가 오기 전에도 프론트~백엔드~DB~실시간이 실제로 도는지 봐야 한다.
Mock 장소("성수동 장소 1")로는 이름·가격·영업시간이 실제와 달라 확인이 안 된다.
```bash
cd backend
python scripts/seed_mock_places.py --dry-run   # 분포만 확인
python scripts/seed_mock_places.py             # 상권 24곳에 3,600여 건 투입
python scripts/verify_places.py                # 상권별 건수·슬롯 분포 확인
python scripts/seed_mock_places.py --clear     # 실데이터가 들어오면 시드만 삭제
```
- 벤더 키가 **하나도 없고** 시드가 DB 에 있으면 검색이 자동으로 시드를 쓴다
  (`app/adapters/seeded.py`). 키가 하나라도 생기면 그쪽이 우선이다.
- 시드에는 `is_mock` 표시가 붙어 `--clear` 로 한 번에 지운다(실데이터는 남는다).
- 같은 시드값이면 id 가 같아 다시 돌려도 중복이 생기지 않는다.

## 상권 배치 확인
```bash
python scripts/districts_map.py     # districts_map.html + 겹침 목록
```
좌표는 대표 역·랜드마크 기준으로 맞춰 두었고(테스트가 300m 이내로 고정),
붙어 있는 상권은 같은 원을 두 번 훑지 않도록 반경을 줄여 잡았다.
## 첫 기동 체크리스트
서버에 처음 올릴 때 이 순서로 확인한다. 각 단계가 끝나야 다음이 의미가 있다.

1. **컨테이너가 다 healthy 인가**
   ```bash
   docker compose -f docker-compose.prod.yml ps      # 전부 (healthy)
   curl -s https://api.${DOMAIN}/health | jq         # db·integrations 확인
   curl -s -o /dev/null -w '%{http_code}\n' https://api.${DOMAIN}/health/ready   # 200
   ```
   `/health/ready` 가 503 이면 DB 미연결이거나 필수 설정이 빠진 것이다.
2. **외부 연동 스모크** — 키를 넣은 만큼만 PASS, 나머지는 SKIP
   ```bash
   docker compose -f docker-compose.prod.yml exec -T backend python scripts/smoke_all.py
   ```
3. **폐업 대장 내려받기 + 시군구 커버리지**
   ```bash
   docker compose -f docker-compose.prod.yml exec -T backend python scripts/fetch_localdata.py
   ```
4. **백업 한 번 손으로 돌려 본다** — 크론이 처음 도는 새벽에 실패를 발견하면 늦다
   ```bash
   ./scripts/ops/backup.sh && ls -lh /var/backups/coursepilot
   ```
5. **크론 확인** — `deploy.sh` 가 설치한다
   ```bash
   crontab -l | sed -n '/coursepilot/,/coursepilot/p'
   ```
6. 여기까지 통과하면 상권 수집(`scripts/build_places.py`)을 돌린다.

## 운영 스크립트 (`scripts/ops/`)
| 스크립트 | 하는 일 |
|---|---|
| `backup.sh` | `pg_dump` → gzip, `BACKUP_DIR`(기본 `/var/backups/coursepilot`)에 보관. `BACKUP_KEEP_DAYS`(기본 7)일 초과분 삭제. 어느 단계에서 실패해도 웹훅 알림 |
| `disk_check.sh` | `DISK_ALERT_PERCENT`(기본 85%) 초과 시 웹훅 알림 |
| `notify.sh` | 위 둘이 쓰는 알림 전송(`ALERT_WEBHOOK_URL`, 미설정 시 로그) |
| `crontab.txt` | 크론 항목 원본(`{{ROOT}}` 치환) |
| `install_cron.sh` | crontab 설치·갱신(기존 사용자 항목은 보존, CoursePilot 블록만 교체) |

크론은 `deploy.sh` 가 자동 설치한다(`INSTALL_CRON=false` 로 끌 수 있다).
로그는 `/var/log/coursepilot/` 아래에 쌓인다.

## 첫 데이터 구축 순서
```bash
cd backend
# ① 폐업 대장 먼저 — 이게 없으면 문 닫은 가게가 그대로 코스에 들어간다
python scripts/fetch_localdata.py                 # 내려받기 + 시군구 커버리지 확인
python scripts/fetch_localdata.py --check-only    # 이미 받아 둔 파일만 점검
# ② 상권 수집(카카오 키만 있으면 된다. Google 단계는 자동으로 건너뛴다)
python scripts/build_places.py
# ③ 결과 점검
python scripts/verify_places.py
```
- **첫 줄 로그**에 카카오 콜 수와 예상 소요가 찍힌다(24개 상권 = 최대 288콜, 약 2분).
- 중간에 죽어도(네트워크·rate limit) **다시 실행하면 남은 조각부터 이어서** 한다.
  진행 상태는 `BATCH_STATE_DIR`(기본 `/tmp`)에 남는다. 처음부터 돌리려면 `--no-resume`.
- 실패한 조각은 끝낸 것으로 치지 않으므로 다음 실행에서 그 조각만 다시 시도한다.
- **Google 키는 나중에 넣어도 된다.** 재실행하면 이미 채운 것은 건너뛰고 남은 것부터
  이어서 채운다 — 매일 재수집이 어제 채운 값을 덮어쓰지 않는다.
- `fetch_localdata.py` 는 24개 상권이 속한 **11개 시군구**(성동·마포·용산·중·종로·강남·
  영등포·광진·송파·서대문·분당)를 다 덮는지 확인하고, 빠진 곳과 영향받는 상권을 찍는다.
- `verify_places.py` 는 상권별 건수 / 슬롯 미매핑 / 폐업 잔존 / Google 매핑률을 보여 준다.

## 프로덕션 안전장치
- **기동 거부(fail fast)** — `ENV`(또는 `APP_ENV`)`=production` 인데 `SESSION_SECRET`,
  `ADMIN_TOKEN` 이 비었거나 DB 비밀번호가 개발 기본값(`coursepilot:coursepilot`)이면
  **앱이 뜨지 않는다.** 경고만 남기고 뜨면 아무도 안 보고, 그 사이 관리 엔드포인트가 열린다.
- **rate limit 은 신뢰 프록시 뒤에서만 헤더를 본다** — Caddy 뒤에서는 소켓 주소가 전부
  프록시라 그대로 쓰면 한 사람이 제한을 채웠을 때 모두가 막힌다. 그렇다고 헤더를 무조건
  믿으면 아무나 지어내 우회한다. `TRUSTED_PROXIES`(기본: 루프백 + 사설망)에서 온 요청만
  `X-Forwarded-For` 를 보고, 그중 **프록시가 덧붙인 맨 오른쪽** 값을 쓴다.
- **운영에서 SMS 키가 없으면 인증 요청을 거절한다(503)** — 개발 폴백은 인증번호를 응답에
  그대로 돌려준다. 운영에서 그러면 누구나 남의 번호로 가입할 수 있다.
- **민감값 마스킹** — 전화번호·인증번호·토큰은 로그에 남기지 않는다(`app/log_safe.py`,
  회귀 테스트가 실제 요청 로그를 훑어 확인한다). 요청 로그는 쿼리스트링을 남기지 않는다.
- **컨테이너 로그 로테이션** — 전 서비스 `json-file` 10MB × 3개. 100GB 디스크가 조용히
  차는 것을 막는다.
- **헬스체크** — db(`pg_isready`) / backend(`/health`) / frontend(`/`) / caddy(관리 API).
  `docker compose ps` 로 상태가 바로 보이고, frontend 는 backend 가 healthy 여야 뜬다.
  `GET /health` 는 DB 연결 여부와 외부 연동(키) 상태를 함께 돌려준다.

## 운영 주의
- **`SESSION_SECRET` 을 반드시 설정한다.** 없으면 `X-User-Id` 헤더만으로 신원이 인정돼, 사용자 id 를 아는 사람이 남의 크레딧을 쓰고 계정을 지울 수 있다(가입 시 내려주는 서명 토큰을 서버가 검증하지 않는다).
- Socket.IO는 WebSocket 사용 — 리버스 프록시(Nginx 등)에서 `Upgrade` 헤더 전달 필요.
- 다중 백엔드 인스턴스로 확장 시 Socket.IO는 메시지 브로커(예: Redis) 어댑터가 필요(현재 단일 프로세스 기준).
- 크레딧 원자적 차감은 DB 행 잠금(`FOR UPDATE`)에 의존 — 인메모리 폴백은 단일 프로세스에서만 정확.

## 장소 데이터 배치 (크론)
장소 DB 는 검색 API 로 즉석에서 만드는 대신 배치로 쌓고 주기적으로 갱신한다.
유료 콜은 무료 한도 안에서 페이싱되며, 한도를 넘기면 호출 자체가 차단된다(`app/quota.py`).

실제 항목은 `scripts/ops/crontab.txt` 에 있고 `deploy.sh` 가 설치한다.
배치는 백엔드 컨테이너 안에서 돈다(파이썬·의존성이 거기 있다).

| 시각 | 작업 |
|---|---|
| 월 02:00 | 폐업 대장(LOCALDATA) 내려받기 |
| 매일 03:00 | 상권 수집·보강 |
| 매일 04:30 | 저장된 장소 갱신(TTL 기준) |
| 매일 05:00 | DB 백업 |
| 6시간마다 | 디스크 사용률 점검 |

- 실행이 겹치면 뒤에 뜬 쪽이 종료 코드 1 로 빠진다(`batch_lock`). 크론 중복은 걱정하지 않아도 된다.
- 초기 구축은 며칠 걸린다 — 영업시간·평점을 하루 할당량씩 채우는 것이 설계 전제다.
- 운영 화면은 `/admin/dashboard`(폴백률·잔여 한도·학습 신호를 한눈에, 30초 갱신).
- 사용량은 `GET /admin/metrics` 의 `quotas` 로 확인하고, 80%·소진 시점에는 `ALERT_WEBHOOK_URL` 로 알림이 간다.

### 키 오기 전 리허설
```bash
# 합성 데이터로 수집→필터→저장 전 구간을 돌려 스키마·용량·페이싱을 확인한다
python scripts/build_places.py --sample --district 성수 연남
```
실제 장소가 아니므로 운영에서는 쓰지 않는다. 배치는 앱과 별개 프로세스라
`DATABASE_URL` 이 있어야 결과가 남는다(없으면 경고만 남기고 인메모리로 끝난다).

### 키 주의
- Google Cloud 콘솔에서 **키 제한(IP/HTTP 리퍼러)과 일일 할당량 상한**을 반드시 설정한다. 코드 쪽 한도는 인스턴스 기준이라 최후 방어선이 아니다.
- 네이버 경로는 NCP 전용 키(`NCP_API_KEY_ID/KEY`)를 쓴다. 개발자센터 키(`NAVER_CLIENT_ID/SECRET`)는 지역·블로그 검색용이다.
