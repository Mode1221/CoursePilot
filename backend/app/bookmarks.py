"""북마크 저장소 (9-4). DB/인메모리 폴백."""
from __future__ import annotations

from app.db import is_ready


class BookmarkStore:
    def __init__(self) -> None:
        self._mem: set[tuple[str, str]] = set()

    def add(self, user_id: str, course_id: str) -> bool:
        """새로 추가되면 True, 이미 북마크된 상태면 False.

        호출부가 인기 신호를 한 번만 반영할 수 있도록 결과를 알려준다.
        """
        if is_ready():
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
                if exists:
                    return False
                s.add(BookmarkModel(user_id=user_id, course_id=course_id))
                s.commit()
            return True
        if (user_id, course_id) in self._mem:
            return False
        self._mem.add((user_id, course_id))
        return True

    def remove(self, user_id: str, course_id: str) -> bool:
        """실제로 지워졌으면 True(없던 북마크면 False)."""
        if is_ready():
            from sqlalchemy import delete

            from app.db import SessionLocal
            from app.models import BookmarkModel

            with SessionLocal() as s:
                result = s.execute(
                    delete(BookmarkModel).where(
                        BookmarkModel.user_id == user_id,
                        BookmarkModel.course_id == course_id,
                    )
                )
                s.commit()
            return bool(result.rowcount)
        if (user_id, course_id) not in self._mem:
            return False
        self._mem.discard((user_id, course_id))
        return True

    def list_course_ids(self, user_id: str, limit: int = 50) -> list[str]:
        """북마크한 코스 id 최근 순. 응답이 계속 커지지 않도록 상한을 둔다."""
        if is_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import BookmarkModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(BookmarkModel.course_id)
                    .where(BookmarkModel.user_id == user_id)
                    .order_by(BookmarkModel.created_at.desc())
                    .limit(limit)
                ).all()
                return [r[0] for r in rows]
        return [cid for (uid, cid) in self._mem if uid == user_id][:limit]


bookmark_store = BookmarkStore()
