"""Socket.IO 실시간 broadcast (5-4). 세션별 room으로 상태 변경 전파."""
from __future__ import annotations

import logging

import socketio

from app.config import settings

logger = logging.getLogger("coursepilot")

def _client_manager() -> socketio.AsyncManager | None:
    """REDIS_URL 이 있으면 Redis pub/sub 매니저(다중 인스턴스), 없으면 None(단일 프로세스).

    redis 패키지/서버가 없는 환경에서도 기동은 막지 않는다(경고 후 단일 프로세스 폴백).
    """
    if not settings.multi_instance:
        return None
    try:
        return socketio.AsyncRedisManager(settings.redis_url)
    except Exception:  # pragma: no cover - 의존성/접속 실패
        logger.warning("REDIS_URL 이 설정됐지만 Redis 매니저 초기화 실패 → 단일 프로세스로 동작")
        return None


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins,
    client_manager=_client_manager(),
)


@sio.event
async def connect(sid, environ, auth):
    pass


@sio.event
async def join(sid, data):
    """참가자가 코스 room에 입장."""
    course_id = data.get("course_id")
    if course_id:
        await sio.enter_room(sid, course_id)
        await sio.emit("joined", {"course_id": course_id}, to=sid)


@sio.event
async def leave(sid, data):
    """코스 화면을 떠나면 room 에서 나간다.

    나가지 않으면 다른 코스로 이동한 뒤에도 이전 코스의 브로드캐스트가 계속
    전달되어 대역폭과 서버 메모리를 낭비한다.
    """
    course_id = data.get("course_id")
    if course_id:
        await sio.leave_room(sid, course_id)
        await sio.emit("left", {"course_id": course_id}, to=sid)


async def broadcast_state(course_id: str, course_dict: dict) -> None:
    await sio.emit("state", course_dict, room=course_id)


async def broadcast_lock(course_id: str, locked: bool) -> None:
    event = "locked" if locked else "unlocked"
    await sio.emit(event, {"course_id": course_id}, room=course_id)


async def broadcast_progress(course_id: str, stage: str) -> None:
    """AI 처리 단계 실시간 전송 (5-4)."""
    await sio.emit("progress", {"course_id": course_id, "stage": stage}, room=course_id)


async def broadcast_message(course_id: str, role: str, text: str) -> None:
    """채팅 메시지 실시간 전송 (5-2)."""
    await sio.emit("message", {"role": role, "text": text}, room=course_id)
