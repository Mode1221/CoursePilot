"""상시 조건(반려동물 동반·주차 필요)은 매 요청에 자동 반영한다."""
from fastapi.testclient import TestClient

from app.main import api
from app.pipeline.agent import _apply_preferences
from app.schemas import PlanConstraints

client = TestClient(api)


def test_요청_키워드에_더한다():
    c = PlanConstraints()
    _apply_preferences(c, {"must_haves": ["반려동물", "주차"]})
    assert c.keywords == ["반려동물", "주차"]


def test_이미_말한_조건은_중복하지_않는다():
    c = PlanConstraints(keywords=["반려동물"])
    _apply_preferences(c, {"must_haves": ["반려동물"]})
    assert c.keywords == ["반려동물"]


def test_설정하지_않으면_아무것도_더하지_않는다():
    c = PlanConstraints()
    _apply_preferences(c, {})
    assert c.keywords == []


def test_저장하고_돌려받는다():
    uid = client.post("/signup", json={"phone": "010-8282-0001"}).json()["user_id"]
    prefs = {"must_haves": ["반려동물"]}
    client.put(f"/users/{uid}/preferences", headers={"X-User-Id": uid}, json=prefs)
    got = client.get(f"/users/{uid}/preferences", headers={"X-User-Id": uid}).json()
    assert got["must_haves"] == ["반려동물"]
