"""학습 신호 관측 엔드포인트."""
from fastapi.testclient import TestClient

from app.feedback import feedback_store
from app.main import api

client = TestClient(api)


def test_표본이_없으면_만족도는_None():
    feedback_store._mem.clear()
    body = client.get("/admin/signals").json()
    assert body["satisfaction_rate"] is None
    assert body["completed_count"] == 0


def test_만족도_비율을_계산한다():
    feedback_store._mem.clear()
    for _ in range(3):
        feedback_store.log("c1", "liked")
    feedback_store.log("c1", "disliked")
    feedback_store.log("c1", "completed")
    body = client.get("/admin/signals").json()
    assert body["satisfaction_rate"] == 0.75
    assert body["completed_count"] == 1


def test_온보딩_설문_응답률을_집계한다():
    import itertools

    from fastapi.testclient import TestClient

    from app.main import api
    from app.users import user_store

    client = TestClient(api)
    phones = itertools.count(1)
    before = user_store.preference_stats()

    uid = client.post(
        "/signup", json={"phone": f"010-5252-{next(phones):04d}"}
    ).json()["user_id"]
    client.post("/signup", json={"phone": f"010-5252-{next(phones):04d}"})  # 미응답 사용자
    client.put(
        f"/users/{uid}/preferences",
        headers={"X-User-Id": uid},
        json={"mood": "조용한", "budget": "2~4만원", "diet": ["비건"]},
    )

    stats = user_store.preference_stats()
    assert stats["users"] >= before["users"] + 2
    assert stats["answered_any"] >= before["answered_any"] + 1
    assert stats["filled_by_question"]["budget"] >= 1
    assert stats["budget_distribution"]["2~4만원"] >= 1
    assert stats["mood_distribution"]["조용한"] >= 1
    assert stats["diet_distribution"]["비건"] >= 1
    assert 0 <= stats["answered_rate"] <= 1
