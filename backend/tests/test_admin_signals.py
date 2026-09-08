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
