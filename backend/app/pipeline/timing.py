"""요청 한 번의 단계별 소요 시간(운영 점검용). QA 요청에서만 응답에 싣는다.

켜지 않은 요청에서는 기록하지 않는다(비용 0). `with stage("search"):` 로 감싼다.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_log: ContextVar[list[tuple[str, int]] | None] = ContextVar("coursepilot_timings", default=None)


def begin() -> None:
    _log.set([])


def snapshot() -> list[tuple[str, int]] | None:
    return _log.get()


@contextmanager
def stage(name: str) -> Iterator[None]:
    log = _log.get()
    if log is None:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        log.append((name, int((time.perf_counter() - t0) * 1000)))


def note(name: str, value: int) -> None:
    log = _log.get()
    if log is not None:
        log.append((name, value))
