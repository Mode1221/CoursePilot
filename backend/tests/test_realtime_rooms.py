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
    assert emitted == ["joined"]


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
    assert emitted == ["left"]


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
