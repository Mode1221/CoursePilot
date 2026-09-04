"""채팅 로그 저장소 (5-2 append-only). DB/인메모리 폴백."""
from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # user | ai
    text: str


class ChatStore:
    def __init__(self) -> None:
        self._mem: dict[str, list[ChatMessage]] = defaultdict(list)
        self._db_ready = False

    def enable_db(self, ready: bool) -> None:
        self._db_ready = ready

    def append(self, course_id: str, role: str, text: str) -> ChatMessage:
        msg = ChatMessage(role=role, text=text)
        if self._db_ready:
            from app.db import SessionLocal
            from app.models import ChatMessageModel

            with SessionLocal() as s:
                s.add(ChatMessageModel(course_id=course_id, role=role, text=text))
                s.commit()
            return msg
        self._mem[course_id].append(msg)
        return msg

    def list(self, course_id: str) -> list[ChatMessage]:
        if self._db_ready:
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import ChatMessageModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(ChatMessageModel.role, ChatMessageModel.text)
                    .where(ChatMessageModel.course_id == course_id)
                    .order_by(ChatMessageModel.created_at, ChatMessageModel.id)
                ).all()
                return [ChatMessage(role=r[0], text=r[1]) for r in rows]
        return list(self._mem[course_id])


chat_store = ChatStore()
