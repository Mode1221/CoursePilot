"""관측성 + 보안 미들웨어: 요청 로깅, 간단한 인메모리 rate limit."""
from __future__ import annotations

import logging
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("coursepilot")

# 생성된 rate limiter 인스턴스 레지스트리(테스트 격리용 리셋 훅)
_RATE_LIMITERS: list[RateLimitMiddleware] = []


def reset_rate_limits() -> None:
    """모든 rate limiter의 카운터 초기화. 테스트 간 격리에 사용."""
    for mw in _RATE_LIMITERS:
        mw._hits.clear()


class RequestLogMiddleware(BaseHTTPMiddleware):
    """메서드/경로/상태/소요시간 구조적 로깅."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
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
