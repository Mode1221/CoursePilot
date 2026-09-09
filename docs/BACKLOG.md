# 백로그 (남은 과제 · 착수 지점)

우선순위 순. 상태 표기는 docs/STATUS.md 와 동일. 각 항목에 관련 파일·시작점을 명시.

## P0 — 실서비스 개시 필수
1. **실배포** (🔑)
   - VM(오라클 프리티어/Lightsail) → DNS A레코드(`도메인`, `api.도메인`) → `cp .env.prod.example .env` → `./deploy.sh`.
   - 파일: `docker-compose.prod.yml`, `Caddyfile`, `deploy.sh`, `docs/DEPLOY.md`.
2. **외부 연동 실호출 검증** (🔑) — 키 주입 후 각 벤더 응답/엔드포인트 실확인.
   - LLM: `app/pipeline/llm.py`, `app/llm_client.py` (Anthropic Haiku).
   - 지도: `app/adapters/naver.py` (특히 길찾기 NCP 엔드포인트 최신화 확인), 좌표 변환.
   - 평점: `app/adapters/google.py` (Text Search 매칭 정확도).
   - SMS/결제: `app/adapters/sms.py`, `app/adapters/payment.py` (NHN 응답 header, 포트원 v1 토큰/조회).

## P1 — 품질·데이터
0. **자연어 커버리지 확대** — 지역·시각·범위·키워드·편집에 더해 인원수(`test_party_size.py`), 날짜(`test_plan_date.py`), 방문 개수(`test_stop_count.py`), 카테고리 지목 편집(`test_edit_by_category.py`), 출발지 지정(`test_start_place.py`), 이동수단 혼합(`test_mixed_travel.py`), 우천 대체(`test_rainy_course.py`), 주말 날짜(`test_plan_date.py`)까지 처리.
3. **리뷰 RAG 고도화** (🟡/⬜) — 약관 준수(요약 금지 소스 구분) 내 데이터 강화. 재수집 중복 저장·협찬 표시 리뷰 검색 제외는 처리됨.
   - 파일: `app/reviews/{source,rag,embedding,sponsored}.py`, `docs/REVIEW_DATA_SOURCES.md`.
4. **목적함수 계수 튜닝** (🟡) — 계수는 `pipeline/weights.py` 단일 출처, 오프라인 탐색 하네스(`pipeline/calibration.py` + `backend/scripts/calibrate.py`)와 합성 신호 리플레이(`pipeline/simulation.py` + `backend/scripts/replay_signals.py`) 완비. 남은 일: 실사용 라벨(`outcome.py`/`strategy.py`/`feedback`) 을 JSONL 로 내보내 실제 계수 갱신.
5. **개인화 벡터(pgvector)** (⬜) — 현재 `behavior.py`(카테고리 빈도)로 대체 중. 임베딩 기반 확장 여지.

## P2 — 운영·확장
6. **다중 인스턴스 확장** (🔑) — `REDIS_URL` 설정 시 Socket.IO Redis 매니저 사용(미설정=단일 프로세스). 남은 일: compose 에 redis 서비스 추가 + 실제 2인스턴스 검증. `app/realtime.py`.
7. **관측성 강화** (🟡) — 구조적 로깅 + 인메모리 메트릭(`GET /admin/metrics`, `app/metrics.py`)에 외부 연동 폴백 비율·임계 알림(`alerts`) 포함. 임계 진입·회복 시 경고 로그. 임계 진입·회복 시 웹훅 발송(`app/alerting.py`, `ALERT_WEBHOOK_URL`, 미설정 시 로그 폴백·15분 재알림 억제). 남은 일: 외부 에러 트래킹(Sentry 등) 연동, 다중 인스턴스 집계.
8. **행정** (코드 밖) — 포트원 가맹계약, SMS 발신번호 등록, 개인정보처리방침.

## 참고
- 푸시 전 로컬 검증: `./scripts/check.sh` (E2E 포함은 `--e2e`).
- 전체 현황: `docs/STATUS.md` / 아키텍처: `docs/ARCHITECTURE.md` / 데이터 전략: `docs/DATA_STRATEGY.md`.
