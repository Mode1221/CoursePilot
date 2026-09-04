"""북마크 저장소 (9-4). DB/인메모리 폴백."""
from __future__ import annotations


class BookmarkStore:
    def __init__(self) -> None:
        self._mem: set[tuple[str, str]] = set()
        self._db_ready = False

    def enable_db(self, ready: bool) -> None:
        self._db_ready = ready

    def add(self, user_id: str, course_id: str) -> None:
        if self._db_ready:
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import BookmarkModel

            with SessionLocal() as s:
                exists = s.execute(
                    select(BookmarkModel.id).where(
                        BookmarkModel.user_id == user_id,
                        BookmarkModel.course_id == course_id,
                    )
                ).first()
                if not exists:
                    s.add(BookmarkModel(user_id=user_id, course_id=course_id))
                    s.commit()
            return
        self._mem.add((user_id, course_id))

    def remove(self, user_id: str, course_id: str) -> None:
        if self._db_ready:
            from sqlalchemy import delete

            from app.db import SessionLocal
            from app.models import BookmarkModel

            with SessionLocal() as s:
                s.execute(
                    delete(BookmarkModel).where(
                        BookmarkModel.user_id == user_id,
                        BookmarkModel.course_id == course_id,
                    )
                )
                s.commit()
            return
        self._mem.discard((user_id, course_id))

    def list_course_ids(self, user_id: str) -> list[str]:
        if self._db_ready:
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import BookmarkModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(BookmarkModel.course_id)
                    .where(BookmarkModel.user_id == user_id)
                    .order_by(BookmarkModel.created_at.desc())
                ).all()
                return [r[0] for r in rows]
        return [cid for (uid, cid) in self._mem if uid == user_id]


bookmark_store = BookmarkStore()
