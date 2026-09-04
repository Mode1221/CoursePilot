# CoursePilot

코파일럿 기반 자율 검증형 모임 동선 플래너. 자연어 조건을 입력하면 장소/지도 API로 물리적 제약(영업시간·이동거리)을 검증한 최적 타임라인을 생성한다.

## 구조
- `/frontend` — Next.js + TS + Zustand (분할 화면: 지도 + 챗봇)
- `/backend` — FastAPI + PostgreSQL/pgvector + Socket.IO (에이전틱 검증 파이프라인)
- `/docs` — 기획안

## 빠른 시작

### 1. DB (선택)
```bash
docker compose up -d db
```
DB 없이도 백엔드는 인메모리 폴백으로 동작한다(개발용).

### 2. 백엔드
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # OPENAI/NAVER 키는 선택 (없으면 Mock/규칙 폴백)
uvicorn main:app --reload
```

### 3. 프론트
```bash
cd frontend
pnpm install
cp .env.local.example .env.local
pnpm dev
```

## 테스트
```bash
cd backend && pytest
cd frontend && pnpm test
```

## 핵심 설계
- **할루시네이션 차단**: LLM은 문장 파싱 + 도구 호출만. 사실 정보는 장소/지도 API가 제공, 검증 단계에서 위반 장소 폐기.
- **어댑터 레이어**: 벤더 직접 호출 금지. `mapService` / `shareService` 경유.
- **동시 편집**: 액션 큐 직렬화 + AI 처리 중 Lock broadcast (Socket.IO room).
- **RAG**: 리뷰는 협찬 필터 후 pgvector 임베딩 저장, 검색 참조.
- **크레딧**: AI 명령만 차감, 수동 편집 무료. 사용량은 "질문 N회"로 노출.

키(OpenAI/Naver) 미설정 시 전 구간 Mock/폴백으로 동작하여 오프라인 개발이 가능하다.
