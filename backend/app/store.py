"""코스 상태 저장소.

DB 사용 가능 시 PostgreSQL 영속화, 불가 시 인메모리(dict) 폴백.
공유 URL = 코스 id (URL-safe 토큰).
"""
from __future__ import annotations

import secrets

from app.schemas import Course


class CourseStore:
    def __init__(self) -> None:
        self._mem: dict[str, Course] = {}
        self._db_ready = False

    def enable_db(self, ready: bool) -> None:
        self._db_ready = ready

    def create(self, title: str = "새 코스", owner_id: str | None = None) -> Course:
        course = Course(id=secrets.token_urlsafe(8), title=title, owner_id=owner_id)
        return self.save(course)

    def list_by_owner(self, owner_id: str) -> list[Course]:
        if self._db_ready:
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import CourseModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(CourseModel.state)
                    .where(CourseModel.owner_id == owner_id)
                    .order_by(CourseModel.updated_at.desc())
                ).all()
                return [Course.model_validate(r[0]) for r in rows]
        return [c for c in self._mem.values() if c.owner_id == owner_id]

    def get(self, course_id: str) -> Course | None:
        if self._db_ready:
            from app.db import SessionLocal
            from app.models import CourseModel

            with SessionLocal() as s:
                row = s.get(CourseModel, course_id)
                if row is None:
                    return None
                return Course.model_validate(row.state)
        return self._mem.get(course_id)

    def save(self, course: Course) -> Course:
        if self._db_ready:
            from app.db import SessionLocal
            from app.models import CourseModel

            with SessionLocal() as s:
                row = s.get(CourseModel, course.id)
                state = course.model_dump(mode="json")
                if row is None:
                    row = CourseModel(id=course.id, title=course.title, state=state)
                    s.add(row)
                row.title = course.title
                row.region = course.region
                row.owner_id = course.owner_id
                row.state = state
                s.commit()
            return course
        self._mem[course.id] = course
        return course


store = CourseStore()
