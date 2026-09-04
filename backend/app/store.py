"""코스 상태 저장소.

초기 구현은 인메모리(dict). 추후 PostgreSQL(pgvector) 영속화로 교체.
"""
from __future__ import annotations

import secrets

from app.schemas import Course


class CourseStore:
    def __init__(self) -> None:
        self._courses: dict[str, Course] = {}

    def create(self, title: str = "새 코스") -> Course:
        course_id = secrets.token_urlsafe(8)
        course = Course(id=course_id, title=title)
        self._courses[course_id] = course
        return course

    def get(self, course_id: str) -> Course | None:
        return self._courses.get(course_id)

    def save(self, course: Course) -> Course:
        self._courses[course.id] = course
        return course


store = CourseStore()
