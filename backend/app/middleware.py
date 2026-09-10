"""관측성 + 보안 미들웨어: 요청 로깅, 간단한 인메모리 rate limit."""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from functools import lru_cache
from ipaddress import ip_address, ip_network

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


@lru_cache(maxsize=1)
def _trusted_networks() -> tuple[ip_network, ...]:
    """설정된 신뢰 프록시 대역. 잘못 적힌 항목은 건너뛴다(기동을 막지 않는다)."""
    from app.config import settings

    nets = []
    for raw in settings.trusted_proxies:
        try:
            nets.append(ip_network(raw, strict=False))
        except ValueError:
            logger.warning("TRUSTED_PROXIES 항목을 해석할 수 없습니다: %r", raw)
    return tuple(nets)


def is_trusted_proxy(host: str) -> bool:
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_networks())


SWEEP_EVERY = 500  # 이 횟수마다 만료된 클라이언트 항목을 정리한다
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
        self._sweeps = 0
        _RATE_LIMITERS.append(self)

    def _client_key(self, request: Request) -> str:
        """rate limit 을 걸 기준 주소.

        Caddy 뒤에서는 소켓 주소가 전부 프록시 IP 라, 그대로 쓰면 한 사람 제한이
        모든 사용자 제한이 된다. 그렇다고 X-Forwarded-For 를 무조건 믿으면 아무나
        헤더를 지어내 제한을 무한히 우회한다.

        그래서 **신뢰하는 프록시에서 온 요청일 때만** 헤더를 본다. 프록시는 받은
        헤더 뒤에 실제 접속자를 덧붙이므로, 믿을 수 있는 값은 **맨 오른쪽**이다
        (왼쪽 항목들은 클라이언트가 지어낼 수 있다).
        """
        peer = request.client.host if request.client else ""
        if not peer:
            return "unknown"
        if not is_trusted_proxy(peer):
            return peer  # 프록시를 거치지 않은 직접 접속 — 헤더는 믿지 않는다
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                return parts[-1]
        return peer

    def _sweep(self, now: float) -> None:
        """오래된 클라이언트 항목 제거(무한 증가 방지)."""
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= now - self._window]
        for key in stale:
            del self._hits[key]

    async def dispatch(self, request: Request, call_next):
        # 헬스체크/문서는 제외
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client = self._client_key(request)
        now = time.time()
        self._sweeps += 1
        if self._sweeps % SWEEP_EVERY == 0:
            self._sweep(now)
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
