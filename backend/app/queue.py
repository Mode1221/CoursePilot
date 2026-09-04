"""세션별 액션 큐 직렬화 + AI 처리 중 Lock (5장 동시 편집 정책).

모든 변경 요청(챗봇/드래그)은 서버 도착 순서대로 세션별 큐에서 순차 처리된다.
한 번에 하나의 AI 요청만 lock을 보유한다.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class SessionQueues:
    """세션(코스)별 asyncio.Lock으로 액션을 직렬화한다."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def is_locked(self, session_id: str) -> bool:
        return self._locks[session_id].locked()

    async def run(self, session_id: str, action: Callable[[], Awaitable[T]]) -> T:
        """세션 큐에 액션을 넣고 도착 순서대로 실행."""
        async with self._locks[session_id]:
            return await action()


queues = SessionQueues()
