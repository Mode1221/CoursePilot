"""관측성 + 보안 미들웨어: 요청 로깅, 간단한 인메모리 rate limit."""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.metrics import metrics_store

logger = logging.getLogger("coursepilot")

# 생성된 rate limiter 인스턴스 레지스트리(테스트 격리용 리셋 훅)
_RATE_LIMITERS: list[RateLimitMiddleware] = []


def reset_rate_limits() -> None:
    """모든 rate limiter의 카운터 초기화. 테스트 간 격리에 사용."""
    for mw in _RATE_LIMITERS:
        mw._hits.clear()


SLOW_REQUEST_MS = 2000  # 이보다 느리면 경고로 남겨 눈에 띄게 한다


class RequestLogMiddleware(BaseHTTPMiddleware):
    """요청 id·메서드·경로·상태·소요시간 구조적 로깅."""

    async def dispatch(self, request: Request, call_next):
        # 클라이언트가 보낸 id 를 우선 존중(프록시/앱에서 이어붙인 추적 id)
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id  # 사용자 신고와 로그를 잇는 고리
        log = logger.warning if elapsed_ms >= SLOW_REQUEST_MS else logger.info
        log(
            "[%s] %s %s -> %d (%.1fms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        # 라우트 템플릿 기준 집계(경로 파라미터가 카디널리티를 늘리지 않도록)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        metrics_store.record(f"{request.method} {path}", response.status_code, elapsed_ms)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """클라이언트(IP)별 슬라이딩 윈도우 rate limit (인메모리, 단일 프로세스 기준).

    분산 배포 시 Redis 등 공유 저장소 기반으로 교체 필요.
    """

    def __init__(self, app, limit: int = 60, window_sec: int = 60) -> None:
        super().__init__(app)
        self._limit = limit
        self._window = window_sec
        self._hits: dict[str, deque[float]] = {}
        _RATE_LIMITERS.append(self)

    async def dispatch(self, request: Request, call_next):
        # 헬스체크/문서는 제외
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        q = self._hits.setdefault(client, deque())
        while q and q[0] <= now - self._window:
            q.popleft()
        if len(q) >= self._limit:
            retry = int(self._window - (now - q[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."},
                headers={"Retry-After": str(retry)},
            )
        q.append(now)
        return await call_next(request)
