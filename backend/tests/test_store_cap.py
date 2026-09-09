"""인메모리 코스 저장 상한(DB 미사용 모드)."""
from __future__ import annotations

from app.schemas import Course
from app.store import MAX_MEM_COURSES, CourseStore


def test_상한을_넘으면_오래된_코스부터_버린다():
    store = CourseStore()
    for i in range(MAX_MEM_COURSES + 3):
        store.save(Course(id=f"c{i}", title=f"코스 {i}"))

    assert len(store._mem) == MAX_MEM_COURSES
    assert store.get("c0") is None  # 가장 오래된 것이 밀려났다
    assert store.get(f"c{MAX_MEM_COURSES + 2}") is not None  # 최근 것은 남는다


def test_상한_안에서는_모두_보관한다():
    store = CourseStore()
    for i in range(10):
        store.save(Course(id=f"k{i}", title=f"코스 {i}"))
    assert len(store._mem) == 10
    assert store.get("k0") is not None
