"""처리 상한을 넘긴 생성 요청은 504 로 끊기고, 크레딧은 돌려받는다."""
import asyncio

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)


def _credits(user_id: str) -> int:
    return client.get(
        f"/users/{user_id}/credits", headers={"X-User-Id": user_id}
    ).json()["questions_left"]


def test_생성이_상한을_넘기면_504_이고_크레딧은_환불된다(monkeypatch):
    from app import queue as queue_mod

    monkeypatch.setattr(queue_mod, "ACTION_TIMEOUT_SEC", 0.05)

    user_id = client.post("/signup", json={"phone": "010-5555-0001"}).json()["user_id"]
    before = _credits(user_id)
    course_id = client.post("/courses", headers={"X-User-Id": user_id}).json()["id"]

    async def _hang(*_a, **_k):
        await asyncio.sleep(5)

    import app.main as main_mod

    # 코스 생성 파이프라인이 응답하지 않는 상황을 만든다
    monkeypatch.setattr(main_mod, "generate_course", _hang)

    res = client.post(
        f"/courses/{course_id}/generate",
        json={"text": "성수동 오전 10시 5시간 도보"},
        headers={"X-User-Id": user_id},
    )
    assert res.status_code == 504
    assert _credits(user_id) == before
