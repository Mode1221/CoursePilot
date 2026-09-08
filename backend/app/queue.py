"""세션별 액션 큐 직렬화 + AI 처리 중 Lock (5장 동시 편집 정책).

모든 변경 요청(챗봇/드래그)은 서버 도착 순서대로 세션별 큐에서 순차 처리된다.
한 번에 하나의 AI 요청만 lock을 보유한다.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class SessionQueues:
    """세션(코스)별 asyncio.Lock으로 액션을 직렬화한다.

    락은 사용 중인 세션만 들고 있는다. 대기자가 없어지면 즉시 버려서
    오래 뜬 프로세스에서 코스 수만큼 락이 쌓이지 않게 한다.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._users: dict[str, int] = {}  # 세션별 현재 사용/대기 중인 액션 수

    def is_locked(self, session_id: str) -> bool:
        lock = self._locks.get(session_id)
        return lock is not None and lock.locked()

    async def run(self, session_id: str, action: Callable[[], Awaitable[T]]) -> T:
        """세션 큐에 액션을 넣고 도착 순서대로 실행."""
        lock = self._locks.get(session_id)
        if lock is None:
            lock = self._locks[session_id] = asyncio.Lock()
        self._users[session_id] = self._users.get(session_id, 0) + 1
        try:
            async with lock:
                return await action()
        finally:
            remaining = self._users[session_id] - 1
            if remaining <= 0:
                self._users.pop(session_id, None)
                self._locks.pop(session_id, None)
            else:
                self._users[session_id] = remaining


queues = SessionQueues()
