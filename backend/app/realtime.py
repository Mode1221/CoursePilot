"""Socket.IO 실시간 broadcast (5-4). 세션별 room으로 상태 변경 전파."""
from __future__ import annotations

import socketio

from app.config import settings

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins,
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


async def broadcast_state(course_id: str, course_dict: dict) -> None:
    await sio.emit("state", course_dict, room=course_id)


async def broadcast_lock(course_id: str, locked: bool) -> None:
    event = "locked" if locked else "unlocked"
    await sio.emit(event, {"course_id": course_id}, room=course_id)
