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
5. **편집 명령이면**: `pipeline/edit.py:parse_edit/apply_edit` 로 부분 수정 후 전체 동선 재계산.
6. **저장 + 신호 누적 + 브로드캐스트**: `store.py:save`, 각 학습 스토어 bump, `realtime.py:broadcast_state`.

수동 편집(`POST /courses/{id}/reorder`, `/places`)도 같은 큐를 거치며 AI 미호출·무료.

## 모듈 책임 맵
### 파이프라인 (`app/pipeline/`)
- `agent.py` — 오케스트레이터(분해→검색→검증→완화).
- `decomposition.py` — 규칙 기반 자연어 파서(시각/분·반, 예산, 동행, 키워드).
- `llm.py` — LLM 도구호출 분해(anthropic/openai), 실패 시 규칙 폴백.
- `planner.py` — `score_place`, `desired_slots`, `route_order`, `seq_order`, `_cf_pick`, `course_score`, `plan_course`.
- `validation.py` — `is_open_during`, `build_timeline`, `recompute`(병렬).
- `edit.py` — 편집 명령 파싱/적용, `_infer_mode`.

### 어댑터 (`app/adapters/`) — 벤더 직접호출 금지, 반드시 경유
- `map_service.py` — `MapService` 추상 + `MockMapService` + `SafeMapService`(폴백 래퍼) + `EnrichedMapService`(Google 평점) + `get_map_service()`.
- `naver.py` — 네이버 지역검색/길찾기.
- `google.py` — Google Places 평점 enrich.
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
- `users.py` 회원·크레딧, `auth.py` SMS 인증, `bookmarks.py`, `chat.py`.
- `db.py` 세션/폴백, `queue.py` 액션 큐, `realtime.py` Socket.IO, `middleware.py` rate limit·로깅, `config.py` env 설정.

### 리뷰 (`app/reviews/`) — 약관 주의(REVIEW_DATA_SOURCES.md)
- `source.py` 리뷰 수집(Google 숫자/attribution, 네이버 링크만), `sponsored.py` 협찬 필터, `embedding.py`/`rag.py` 임베딩·검색(제한적).

## 불변 원칙 (깨지 말 것)
1. 지도/장소는 **어댑터 경유만**(벤더 직접호출 금지).
2. 코스 상태 변경은 **액션 큐 직렬화**.
3. 모든 외부연동은 **키 없으면 폴백**(서비스 무중단).
4. DB 준비 여부는 **`db.is_ready()` 단일 소스**만 참조.
5. 학습 스토어는 전역 싱글턴 → 테스트는 `tests/conftest.py` 및 각자 `_mem.clear()` 로 격리.
