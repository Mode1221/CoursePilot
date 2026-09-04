from app.bookmarks import BookmarkStore
from app.store import CourseStore
from app.users import UserStore


def test_list_by_owner():
    st = CourseStore()
    a = st.create("A", owner_id="u1")
    st.create("B", owner_id="u2")
    st.create("C", owner_id="u1")
    mine = st.list_by_owner("u1")
    assert {c.title for c in mine} == {"A", "C"}
    assert a.owner_id == "u1"


def test_bookmarks():
    bs = BookmarkStore()
    bs.add("u1", "c1")
    bs.add("u1", "c2")
    bs.add("u1", "c1")  # 중복 무시
    assert set(bs.list_course_ids("u1")) == {"c1", "c2"}
    bs.remove("u1", "c1")
    assert bs.list_course_ids("u1") == ["c2"]


def test_referral_grant():
    us = UserStore()
    ref = us.create("010-0000-0000", credits_limit=5)
    us.grant_credits(ref.id, 1)
    assert us.get(ref.id).credits_left == 6
