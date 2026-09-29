"""채팅 로그 저장소 (5-2 append-only). DB/인메모리 폴백."""
from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from app.db import is_ready


class ChatMessage(BaseModel):
    role: str  # user | ai
    text: str


# 인메모리 폴백은 개발/비상용이므로 코스당 보관량에 상한을 둔다(무한 증가 방지)
MAX_MEM_MESSAGES = 200


class ChatStore:
    def __init__(self) -> None:
        self._mem: dict[str, list[ChatMessage]] = defaultdict(list)

    def append(self, course_id: str, role: str, text: str) -> ChatMessage:
        msg = ChatMessage(role=role, text=text)
        if is_ready():
            from app.db import SessionLocal
            from app.models import ChatMessageModel

            with SessionLocal() as s:
                s.add(ChatMessageModel(course_id=course_id, role=role, text=text))
                s.commit()
            return msg
        history = self._mem[course_id]
        history.append(msg)
        if len(history) > MAX_MEM_MESSAGES:
            del history[: len(history) - MAX_MEM_MESSAGES]  # 오래된 것부터 버린다
        return msg

    def clear(self, course_id: str) -> None:
        """코스 삭제·회원 탈퇴 시 대화 기록을 함께 지운다(개인정보 최소 보관)."""
        if is_ready():
            from sqlalchemy import delete

            from app.db import SessionLocal
            from app.models import ChatMessageModel

            with SessionLocal() as s:
                s.execute(
                    delete(ChatMessageModel).where(ChatMessageModel.course_id == course_id)
                )
                s.commit()
            return
        self._mem.pop(course_id, None)

    def list(self, course_id: str) -> list[ChatMessage]:
        if is_ready():
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
        return list(self._mem.get(course_id, []))


chat_store = ChatStore()
