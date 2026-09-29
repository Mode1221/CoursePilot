"""영속(DB) 경로 회귀 테스트.

지금까지 테스트는 전부 인메모리 폴백만 지나갔다 — 실제 배포에서 도는 코드는
`is_ready()` 가 True 인 쪽인데 그 분기가 한 번도 실행되지 않았다.
Postgres 없이도 같은 SQLAlchemy 경로를 밟도록 임시 SQLite 파일에 붙여 검증한다.
(pgvector 임베딩 검색만 SQLite 에서 빠지고, 나머지 모델은 그대로 생성된다.)
"""
import pytest

from app.config import settings


@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.db as db_mod

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/t.db")
    # 엔진은 모듈 전역에 캐시된다 — 테스트마다 새 파일을 보게 초기화한다
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    db_mod.set_ready(True)
    yield db_mod
    db_mod.set_ready(False)


def test_회원과_코스가_DB_에_남는다(db):
    from app.store import store
    from app.users import user_store

    user = user_store.create("010-1234-5678")
    course = store.create(owner_id=user.id)
    course.title = "성수동 데이트"
    store.save(course)

    assert store.get(course.id).title == "성수동 데이트"
    assert [c.id for c in store.list_by_owner(user.id)] == [course.id]
    assert store.delete(course.id) is True
    assert store.get(course.id) is None


def test_크레딧_차감과_환불이_DB_에서_원자적이다(db):
    from app.users import CreditError, user_store

    user = user_store.create("010-2222-3333")
    start = user.credits_left

    for _ in range(start):
        user_store.consume_credit(user.id)
    assert user_store.get(user.id).credits_left == 0

    with pytest.raises(CreditError):
        user_store.consume_credit(user.id)

    user_store.refund_credit(user.id)
    assert user_store.get(user.id).credits_left == 1


def test_포인트는_무료_크레딧_소진_후_쓰인다(db):
    from app.users import user_store

    user = user_store.create("010-3333-4444")
    for _ in range(user.credits_left):
        user_store.consume_credit(user.id)

    user_store.purchase_points(user.id, 2)
    assert user_store.get(user.id).credits_left == 2
    user_store.consume_credit(user.id)
    assert user_store.get(user.id).points == 1


def test_같은_결제는_DB_에서도_한_번만_기록된다(db):
    from app.payment_ledger import PaymentLedger

    ledger = PaymentLedger()
    assert ledger.mark_used("imp_db_1", user_id="u1", points=3) is True
    assert ledger.mark_used("imp_db_1", user_id="u1", points=3) is False
    assert ledger.is_used("imp_db_1") is True


def test_북마크_추가_해제가_DB_에_반영된다(db):
    from app.bookmarks import bookmark_store
    from app.store import store
    from app.users import user_store

    user = user_store.create("010-4444-5555")
    course = store.create(owner_id=user.id)

    assert bookmark_store.add(user.id, course.id) is True
    assert bookmark_store.add(user.id, course.id) is False  # 중복은 무시
    assert bookmark_store.list_course_ids(user.id) == [course.id]
    assert bookmark_store.remove(user.id, course.id) is True
    assert bookmark_store.list_course_ids(user.id) == []


def test_탈퇴하면_회원_데이터가_사라진다(db):
    from app.users import user_store

    user = user_store.create("010-5555-6666")
    assert user_store.delete(user.id) is True
    assert user_store.get(user.id) is None
