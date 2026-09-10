"""배치용 DB 연결.

배치는 웹 앱과 별개 프로세스로 돈다. 앱 기동 시에만 DB 를 열면, 배치가 모은
장소가 인메모리에 쌓였다가 프로세스와 함께 사라진다(실제로 그랬다).
"""
from __future__ import annotations

import logging

logger = logging.getLogger("coursepilot")


def connect_db() -> bool:
    """DB 를 열고 readiness 를 세운다. 실패하면 인메모리로 계속 진행."""
    from app.db import init_db, is_ready, set_ready

    if is_ready():
        return True
    ready = init_db()
    set_ready(ready)
    if not ready:
        logger.warning("DB 에 연결하지 못했습니다 — 이번 배치 결과는 저장되지 않습니다.")
    return ready
