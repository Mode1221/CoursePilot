# 아키텍처 (인수인계용)

대화 이력 없이도 코드에 바로 손댈 수 있도록 요청 흐름·모듈 책임·핵심 원칙을 정리한다.

## 큰 그림
- **frontend** (Next.js App Router, Zustand): 지도+채팅 하이브리드 UI. `src/services/api.ts`(REST), `socket.ts`(실시간), `mapService.ts`(지도 어댑터).
- **backend** (FastAPI + python-socketio ASGI): `app/main.py` 가 REST 엔드포인트 + Socket.IO 마운트. 진입점 `app.main:app`(=socketio.ASGIApp).
- **db** (PostgreSQL + pgvector): SQLAlchemy 2.0. **DB 불가 시 전 스토어가 인메모리 폴백** — 단일 소스 `app/db.py:is_ready()`.

## 코스 생성 요청 흐름 (핵심 경로)
`POST /courses/{id}/generate` (main.py) →
1. **큐 직렬화**: `queue.py:queues.run(course_id, action)` — 코스별 액션 직렬화(동시편집 lost update 방지).
2. **크레딧 차감**: `users.py:consume_credit` (DB면 `FOR UPDATE` 원자적). 실패 시 402, 예외 시 환불.
3. **AI Lock 브로드캐스트**: `realtime.py:broadcast_lock` → 참여자 편집 잠금.
4. **파이프라인**: `pipeline/agent.py:generate_course`
   - `pipeline/llm.py:decompose` — 자연어→`PlanConstraints`. Anthropic Haiku(키) 또는 규칙 파서(`pipeline/decomposition.py`) 폴백.
   - `adapters/map_service.py:get_map_service()` — 후보 장소 수집(네이버/Mock, Google 평점 enrich).
   - `pipeline/planner.py:plan_course` — 스코어링·템플릿·동선·Best-of-N.
   - `pipeline/validation.py:build_timeline` — 영업시간·이동시간 물리 검증.
   - 부족 시 조건 완화 재시도(이동시간↑, 소프트 키워드 드롭). 완화 강도는 `feedback.py:acceptance_rate()` 로 학습.
     시도들 중 **장소가 가장 많은 결과**를 채택하므로 완화가 되레 나쁘면 원래 코스가 남는다.
5. **편집 명령이면**: `pipeline/edit.py:parse_edit/apply_edit` 로 부분 수정 후 전체 동선 재계산.
6. **저장 + 신호 누적 + 브로드캐스트**: `store.py:save`, 각 학습 스토어 bump, `realtime.py:broadcast_state`.

수동 편집(`POST /courses/{id}/reorder`, `/places`, `/items`)도 같은 큐를 거치며 AI 미호출·무료.
"조건을 완화할까요?"에 수락하면 `POST /courses/{id}/relax` — 직전 요청 문장으로 완화를 강제해
재구성하며, 새 질문이 아니므로 **크레딧을 쓰지 않는다**.

## 모듈 책임 맵
### 파이프라인 (`app/pipeline/`)
- `agent.py` — 오케스트레이터(분해→검색→검증→완화).
- `decomposition.py` — 규칙 기반 자연어 파서(시각/분·반, 예산, 동행, 키워드, 출발지, 우천, 수단 고정).
- `llm.py` — LLM 도구호출 분해(anthropic/openai), 실패 시 규칙 폴백.
- (backend) `alerting.py` — 임계 알림 웹훅 발송(미설정 시 로그, 재알림 억제).
- (backend) `reasons.py` — 코스 장소 선택 근거 계산(저장 없이 코스+마지막 요청으로).
- `weights.py` — 스코어 계수(`PLACE_WEIGHTS`/`COURSE_WEIGHTS`) 단일 출처.
- `simulation.py` — 합성 사용 신호 생성·리플레이(`simulate_sessions`/`replay`/`rank_quality`), CLI `backend/scripts/replay_signals.py`.
- `calibration.py` — 라벨(JSONL) 기반 오프라인 계수 탐색: `evaluate`(top1/top3/MRR), `calibrate`(좌표 상승), CLI `backend/scripts/calibrate.py`.
- `planner.py` — `score_place`(우천·인원·제외 보정 포함), `desired_slots`, `route_order`/`route_order_from`(출발지 기준), `seq_order`, `_cf_pick`, `course_score`, `plan_course`.
- `validation.py` — `is_open_during`, `best_route`(도보 20분 초과 구간은 대중교통으로 전환), `build_timeline`, `recompute`(병렬).
- `edit.py` — 편집 명령 파싱/적용(교체·삭제·추가), `_infer_mode`.

### 어댑터 (`app/adapters/`) — 벤더 직접호출 금지, 반드시 경유
- `map_service.py` — `MapService` 추상 + `MockMapService` + `SafeMapService`(폴백 래퍼) + `ClosedFilterMapService`(LOCALDATA 폐업 제거·업력 부착) + `CachedSearchMapService(검색 5분 TTL + 경로 캐시)` + `get_map_service()`.
- `kakao.py` — 카카오 로컬 검색(장소 발견 주 원천, `category_group_code`→슬롯). 경로는 네이버에 위임.
- `naver.py` — 네이버 지역검색/길찾기.
- `google.py` — Google Places v1. 티어별 분리 호출(IDs-only 매핑 / Pro 영업시간 / Enterprise 평점, 필드마스크 혼합 금지). 영업시간 30일·평점 90일 TTL, 확정 코스만 런타임 갱신(`refresh_final_hours`).
- `localdata.py` — LOCALDATA(지방행정 인허가) CSV 인덱스. 폐업 판정·인허가일자(업력)·지역 폐업률. 무료·무인증, 주 1회 갱신(`LOCALDATA_CSV_DIR`).
- `sms.py` — NHN Cloud SMS. `payment.py` — 포트원 v1 결제 검증.

### 학습 신호 스토어 (전부 DB/인메모리 폴백, `_db_ready()` 분기)
- `popularity.py` — 장소 인기(채택+1/북마크+2/거부-1/완주+3), 시간감쇠 EWMA.
- `ratings.py` — 원탭 별점 집계. `sequence.py` — 재정렬 카테고리 전이.
- `timecontext.py` — 시간대(데이파트)별 채택. `behavior.py` — 사용자×카테고리 행동선호.
- `cooccurrence.py` — 장소 공동채택(협업필터링). `strategy.py` — Best-of-N 시드 채택.
- `outcome.py` — 예측점수↔만족도 대조. `feedback.py` — 완화 수용/거부 등 이벤트.
- `places.py` — 전역 장소 스냅샷(id→장소 복원, CF 추천용).

### 코어
- `main.py` 엔드포인트, `models.py` ORM, `schemas.py` 도메인, `store.py` 코스 저장.
- `users.py` 회원·크레딧(차감·환불 모두 행 잠금), `auth.py` SMS 인증(시도·발송 제한), `payment_ledger.py` 결제 원장(리플레이 차단, DB/인메모리 폴백), `bookmarks.py`, `chat.py`.
- `db.py` 세션/폴백, `queue.py` 액션 큐, `realtime.py` Socket.IO, `config.py` env 설정.
- `middleware.py` — rate limit + 요청 로깅(요청마다 `X-Request-Id` 발급·응답 반환, 2초 이상은 warning).
- `metrics.py` — 라우트별 지연/에러, 외부 연동 폴백 비율(`externals`), 임계 초과 `alerts`. `GET /admin/metrics`(ADMIN_TOKEN).
- 미처리 예외는 `main.py` 전역 핸들러가 `request_id` 를 담아 응답(내부 스택은 로그로만).

### 리뷰 (`app/reviews/`) — 약관 주의(REVIEW_DATA_SOURCES.md)
- `source.py` 리뷰 수집(Google 숫자/attribution, 네이버 링크만) + `SafeReviewSource` 폴백 래퍼.
- `sponsored.py` 협찬 필터(표기·구조 신호, "내돈내산"은 반대 신호), `aspects.py` 태그 추출.
- `embedding.py`/`rag.py` 임베딩·검색(제한적). 요약 폴백은 **원문 대신 태그**로만 구성.

## 불변 원칙 (깨지 말 것)
1. 지도/장소는 **어댑터 경유만**(벤더 직접호출 금지).
2. 코스 상태 변경은 **액션 큐 직렬화**.
3. 모든 외부연동은 **키 없으면 폴백**(서비스 무중단).
4. DB 준비 여부는 **`db.is_ready()` 단일 소스**만 참조.
5. 학습 스토어는 전역 싱글턴 → 테스트는 `tests/conftest.py` 및 각자 `_mem.clear()` 로 격리.

### 배치 (`app/batch/`)
- `districts.py` — 수집 대상 상권 24곳(좌표·반경).
- `places_build.py` — 상권 전수 수집(카카오) → 폐업 제거(LOCALDATA) → Google 영업시간·평점 페이싱 → upsert.
  실행: `python scripts/build_places.py` (하루 1회, 영업시간 160건/일·평점 11건/일).
