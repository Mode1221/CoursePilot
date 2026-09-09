"""room 입·퇴장 이벤트."""
from __future__ import annotations

from app import realtime


async def test_join_은_room_에_넣는다(monkeypatch):
    entered: list[tuple[str, str]] = []
    emitted: list[str] = []

    async def _enter(sid, room):
        entered.append((sid, room))

    async def _emit(event, data=None, **kw):
        emitted.append(event)

    monkeypatch.setattr(realtime.sio, "enter_room", _enter)
    monkeypatch.setattr(realtime.sio, "emit", _emit)

    await realtime.join("sid1", {"course_id": "c1"})
    assert entered == [("sid1", "c1")]
    # 입장 알림 + 현재 인원수(presence) 브로드캐스트
    assert emitted == ["joined", "presence"]


async def test_leave_는_room_에서_뺀다(monkeypatch):
    left: list[tuple[str, str]] = []
    emitted: list[str] = []

    async def _leave(sid, room):
        left.append((sid, room))

    async def _emit(event, data=None, **kw):
        emitted.append(event)

    monkeypatch.setattr(realtime.sio, "leave_room", _leave)
    monkeypatch.setattr(realtime.sio, "emit", _emit)

    await realtime.leave("sid1", {"course_id": "c1"})
    assert left == [("sid1", "c1")]
    assert emitted == ["left", "presence"]


async def test_코스id_가_없으면_아무것도_하지_않는다(monkeypatch):
    called: list[str] = []

    async def _boom(*a, **kw):
        called.append("x")

    monkeypatch.setattr(realtime.sio, "enter_room", _boom)
    monkeypatch.setattr(realtime.sio, "leave_room", _boom)
    monkeypatch.setattr(realtime.sio, "emit", _boom)

    await realtime.join("sid1", {})
    await realtime.leave("sid1", {})
    assert called == []


async def test_인원수를_room_에_알린다(monkeypatch):
    sent: list[tuple[str, dict]] = []

    async def _emit(event, data=None, **kw):
        sent.append((event, data))

    monkeypatch.setattr(realtime.sio, "emit", _emit)
    monkeypatch.setattr(
        realtime.sio.manager, "rooms", {"/": {"c1": {"sid1": None, "sid2": None}}}
    )

    await realtime.broadcast_presence("c1")
    assert sent == [("presence", {"count": 2})]

    # 나가는 소켓은 세지 않는다
    sent.clear()
    await realtime.broadcast_presence("c1", exclude="sid2")
    assert sent == [("presence", {"count": 1})]
