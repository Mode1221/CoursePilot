"""신호 스토어의 영속(DB) 경로 회귀 테스트.

인기·별점·행동·재방문·동시출현·순서·성과·피드백·대화는 모두 인메모리 폴백만
검증돼 있었다. 배포에서 도는 SQLAlchemy 경로를 임시 SQLite 로 같이 밟는다.
"""
import pytest

from app.config import settings


@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.db as db_mod

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    db_mod.set_ready(True)
    yield db_mod
    db_mod.set_ready(False)


def test_인기_점수는_누적되고_조회된다(db):
    from app.popularity import popularity_store

    popularity_store.bump("p1")
    popularity_store.bump_many(["p1", "p2"], weight=2)
    scores = popularity_store.scores(["p1", "p2", "없는곳"])
    assert scores["p1"] > scores["p2"] > 0
    assert scores.get("없는곳", 0) == 0


def test_별점_평균이_DB_에_쌓인다(db):
    from app.ratings import rating_store

    rating_store.submit("p1", 5)
    rating_store.submit("p1", 3)
    assert rating_store.averages(["p1"])["p1"] == pytest.approx(4.0)


def test_별점_수정은_이전_점수를_대체한다(db):
    from app.ratings import rating_store

    rating_store.submit("p2", 1)
    rating_store.submit("p2", 5, replaces=1)
    assert rating_store.averages(["p2"])["p2"] == pytest.approx(5.0)


def test_행동_선호는_자주_고른_카테고리를_돌려준다(db):
    from app.behavior import behavior_store

    for _ in range(3):
        behavior_store.bump("u1", ["카페"])
    behavior_store.bump("u1", ["술집"])
    assert behavior_store.top_categories("u1") == ["카페"]


def test_재방문_표시는_한_번만_기록된다(db):
    from app.revisits import revisit_store

    assert revisit_store.mark("u1", "p1") is True
    assert revisit_store.mark("u1", "p1") is False


def test_동시출현으로_함께_간_장소를_찾는다(db):
    from app.cooccurrence import cooccurrence_store

    cooccurrence_store.bump_course(["a", "b", "c"])
    cooccurrence_store.bump_course(["a", "b"])
    partners = dict(cooccurrence_store.top_partners("a"))
    assert partners["b"] > partners.get("c", 0)


def test_순서_통계가_이어지는_카테고리를_선호한다(db):
    from app.sequence import sequence_store

    for _ in range(3):
        sequence_store.bump_sequence(["맛집", "카페"])
    assert sequence_store.transition("맛집", "카페") > 0


def test_예측_점수와_만족도의_분리도를_계산한다(db):
    from app.outcome import outcome_store

    outcome_store.record(0.9, liked=True)
    outcome_store.record(0.2, liked=False)
    assert outcome_store.separation() is not None


def test_피드백_집계와_수용률(db):
    from app.feedback import feedback_store

    feedback_store.log("c1", "relax_accepted")
    feedback_store.log("c1", "relax_rejected")
    assert feedback_store.counts()["relax_accepted"] == 1
    assert 0 <= feedback_store.acceptance_rate() <= 1


def test_대화가_코스별로_저장된다(db):
    from app.chat import chat_store

    chat_store.append("c1", "user", "성수동 코스")
    chat_store.append("c1", "ai", "이렇게 짰어요")
    assert [m.role for m in chat_store.list("c1")] == ["user", "ai"]
    chat_store.clear("c1")
    assert chat_store.list("c1") == []


def test_시간대_신호가_DB_에_쌓인다(db):
    from app.timecontext import daypart_of, time_context_store

    assert daypart_of(9) == "morning"
    time_context_store.bump("p1", "morning")
    time_context_store.bump_many(["p1", "p2"], "morning", weight=2)
    scores = time_context_store.scores(["p1", "p2", "p3"], "morning")
    assert scores["p1"] == 3
    assert scores["p2"] == 2
    assert scores["p3"] == 0  # 기록 없는 장소도 0 으로 채워 준다


def test_시딩_전략_채택수가_DB_에_누적된다(db):
    from app.strategy import strategy_store

    strategy_store.bump("route")
    strategy_store.bump("route", weight=2)
    strategy_store.bump("template")
    counts = strategy_store.counts()
    assert counts["route"] == 3
    assert counts["template"] == 1


def test_장소_카탈로그가_DB_에_저장되고_지워진다(db):
    from app.places import place_repo
    from app.schemas import Place

    places = [
        Place(id="k1", name="성수 카페", category="카페", address="서울", lat=37.54, lng=127.05),
        Place(id="k2", name="성수 맛집", category="맛집", address="서울", lat=37.55, lng=127.06),
    ]
    place_repo.upsert_many(places)
    found = place_repo.get_many(["k1", "k2", "없음"])
    assert found["k1"].name == "성수 카페"
    assert "없음" not in found

    # 같은 id 로 다시 넣으면 갱신(중복 행이 생기지 않는다)
    places[0].name = "성수 카페(이전)"
    place_repo.upsert_many(places)
    assert place_repo.get_many(["k1"])["k1"].name == "성수 카페(이전)"

    assert [p.id for p in place_repo.all()] != []
    assert place_repo.delete_many(["k1"]) == 1
    assert place_repo.get_many(["k1"]) == {}
