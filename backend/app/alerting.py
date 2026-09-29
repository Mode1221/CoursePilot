"""임계 알림 외부 발송 (관측성 P2-7).

메트릭 임계(오류율·폴백률) 진입/회복 순간을 웹훅으로 밀어준다.
`alert_webhook_url` 미설정이면 로그만 남기고 조용히 넘어간다(키 없는 환경 기준).
같은 항목의 반복 알림은 재알림 간격(`RENOTIFY_SEC`)으로 억제한다.
"""
from __future__ import annotations

import asyncio
import logging
from time import monotonic

import httpx

from app.config import settings

logger = logging.getLogger("coursepilot")

RENOTIFY_SEC = 900  # 같은 항목 재알림 최소 간격(15분)
TIMEOUT_SEC = 5


class AlertNotifier:
    _pending: set[asyncio.Task] = set()

    def __init__(self) -> None:
        self._last_sent: dict[str, float] = {}

    def _throttled(self, key: str) -> bool:
        now = monotonic()
        last = self._last_sent.get(key)
        if last is not None and now - last < RENOTIFY_SEC:
            return True
        self._last_sent[key] = now
        return False

    async def send(self, kind: str, target: str, text: str) -> bool:
        """웹훅 발송. 미설정·억제·실패 시 False(호출부는 신경 쓰지 않아도 된다)."""
        key = f"{kind}:{target}"
        if self._throttled(key):
            return False
        if not settings.alert_webhook_url:
            logger.info("알림(웹훅 미설정): %s", text)
            return False
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
                resp = await client.post(
                    settings.alert_webhook_url,
                    json={"text": text, "kind": kind, "target": target},
                )
                resp.raise_for_status()
        except Exception:  # 알림 실패가 본 요청을 깨뜨리면 안 된다
            logger.warning("알림 발송 실패: %s", text)
            return False
        return True

    def notify(self, kind: str, target: str, text: str) -> None:
        """동기 코드(메트릭 기록)에서 부르는 진입점. 이벤트 루프가 있으면 백그라운드로."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.info("알림: %s", text)
            return
        task = loop.create_task(self.send(kind, target, text))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    def clear(self) -> None:
        self._last_sent.clear()


alert_notifier = AlertNotifier()
