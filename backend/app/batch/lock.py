"""배치 중복 실행 방지 락.

크론이 겹치거나 사람이 수동으로 한 번 더 돌리면 유료 콜이 두 배로 나간다.
파일 락이면 컨테이너 하나 안에서만 유효하므로, DB 가 있으면 DB 를 쓴다.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

STALE_AFTER_MIN = 180  # 이 시간이 지난 락은 죽은 프로세스가 남긴 것으로 본다


class LockBusy(RuntimeError):
    """다른 실행이 이미 진행 중."""


def _db_ready() -> bool:
    try:
        from app.db import is_ready

        return is_ready()
    except Exception:
        return False


def _holder() -> str:
    return f"{os.uname().nodename}:{os.getpid()}"


def acquire(name: str, now: datetime | None = None) -> bool:
    """락을 잡으면 True. 이미 누가 잡고 있으면 False."""
    if not _db_ready():
        return True  # DB 없는 개발 환경에서는 막지 않는다
    from app.db import SessionLocal
    from app.models import BatchLockModel

    moment = now or datetime.now(UTC)
    with SessionLocal() as s:
        row = s.get(BatchLockModel, name)
        if row is not None and not _stale(row.acquired_at, moment):
            return False
        if row is None:
            s.add(BatchLockModel(name=name, holder=_holder(), acquired_at=moment))
        else:
            row.holder, row.acquired_at = _holder(), moment
        s.commit()
    return True


def release(name: str) -> None:
    if not _db_ready():
        return
    from app.db import SessionLocal
    from app.models import BatchLockModel

    with SessionLocal() as s:
        row = s.get(BatchLockModel, name)
        if row is not None:
            s.delete(row)
            s.commit()


def _stale(acquired_at: datetime | None, now: datetime) -> bool:
    """죽은 프로세스가 남긴 락은 시간이 지나면 무시한다(영원히 잠기지 않도록)."""
    if acquired_at is None:
        return True
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=UTC)
    return now - acquired_at >= timedelta(minutes=STALE_AFTER_MIN)


@contextmanager
def batch_lock(name: str):
    """배치 실행을 감싼다. 이미 돌고 있으면 LockBusy."""
    if not acquire(name):
        raise LockBusy(f"이미 실행 중인 배치가 있다: {name}")
    try:
        yield
    finally:
        release(name)
