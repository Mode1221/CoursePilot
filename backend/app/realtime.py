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
async def disconnect(sid):
    """연결이 끊기면 남은 참가자에게 인원수를 다시 알린다."""
    for room in _rooms_of(sid):
        await broadcast_presence(room, exclude=sid)


def _rooms_of(sid: str) -> list[str]:
    """이 소켓이 들어가 있는 코스 room 목록(자기 자신 room 제외)."""
    try:
        rooms = sio.rooms(sid)
    except Exception:  # pragma: no cover - 매니저 구현에 따라 조회 불가할 수 있다
        return []
    return [r for r in rooms if r != sid and not r.endswith("#chat")]


def _room_size(course_id: str, exclude: str | None = None) -> int:
    """room 참가자 수. 다중 인스턴스(Redis)에서는 이 인스턴스 기준이다."""
    try:
        participants = sio.manager.rooms.get("/", {}).get(course_id, {})
    except Exception:  # pragma: no cover - 매니저 구현 차이
        return 0
    return len([p for p in participants if p != exclude])


async def broadcast_presence(course_id: str, exclude: str | None = None) -> None:
    """"몇 명이 함께 보고 있는지"를 room 에 알린다 (5-4 선택 항목)."""
    await sio.emit("presence", {"count": _room_size(course_id, exclude)}, room=course_id)


MAX_ROOMS_PER_SOCKET = 3  # 한 화면이 동시에 보는 코스는 1~2개다. 무작위 id 로 방을 늘리지 못하게


@sio.event
async def join(sid, data):
    """참가자가 코스 room에 입장. 있는 코스만, 소켓당 방 수 상한."""
    course_id = data.get("course_id") if isinstance(data, dict) else None
    if not isinstance(course_id, str) or not 0 < len(course_id) <= 64:
        return
    if len(_rooms_of(sid)) >= MAX_ROOMS_PER_SOCKET:
        return
    from app.store import store

    course = store.get(course_id)
    if course is None:
        return
    if course_id:
        await sio.enter_room(sid, course_id)
        # 대화는 만든 사람·같이 정하는 상대만 받는다(공유 링크로 보는 사람에게는 코스 상태만)
        if _can_read_chat(course, data):
            await sio.enter_room(sid, chat_room(course_id))
        await sio.emit("joined", {"course_id": course_id}, to=sid)
        await broadcast_presence(course_id)


def chat_room(course_id: str) -> str:
    return f"{course_id}#chat"


def _can_read_chat(course, data: dict) -> bool:
    from fastapi import HTTPException

    from app.identity import course_editor

    def _s(key: str) -> str | None:
        v = data.get(key)
        return v if isinstance(v, str) and len(v) <= 256 else None

    try:
        course_editor(course, _s("user_id"), _s("user_token"), _s("together_token"))
    except HTTPException:
        return False
    return True


@sio.event
async def leave(sid, data):
    """코스 화면을 떠나면 room 에서 나간다.

    나가지 않으면 다른 코스로 이동한 뒤에도 이전 코스의 브로드캐스트가 계속
    전달되어 대역폭과 서버 메모리를 낭비한다.
    """
    course_id = data.get("course_id") if isinstance(data, dict) else None
    if isinstance(course_id, str) and course_id:
        await sio.leave_room(sid, course_id)
        await sio.leave_room(sid, chat_room(course_id))
        await sio.emit("left", {"course_id": course_id}, to=sid)
        await broadcast_presence(course_id)


async def broadcast_state(course_id: str, course_dict: dict) -> None:
    await sio.emit("state", course_dict, room=course_id)


async def broadcast_lock(course_id: str, locked: bool) -> None:
    event = "locked" if locked else "unlocked"
    await sio.emit(event, {"course_id": course_id}, room=course_id)


async def broadcast_progress(course_id: str, stage: str) -> None:
    """AI 처리 단계 실시간 전송 (5-4)."""
    await sio.emit("progress", {"course_id": course_id, "stage": stage}, room=course_id)


async def broadcast_message(course_id: str, role: str, text: str) -> None:
    """채팅 메시지 실시간 전송 (5-2). 대화 방(편집 권한자)에만."""
    await sio.emit("message", {"role": role, "text": text}, room=chat_room(course_id))
