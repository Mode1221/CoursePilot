"""편집 결과 안내는 무엇이 바뀌었는지 말한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-2828-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return uid, cid


def _say(uid: str, cid: str, text: str) -> str:
    client.post(f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": text})
    return client.get(f"/courses/{cid}/messages").json()[-1]["text"]


def test_교체는_몇_번째를_무엇으로_바꿨는지_말한다():
    uid, cid = _course()
    text = _say(uid, cid, "2번째를 카페로 바꿔줘")
    assert "2번째를" in text and "바꿨어요" in text


def test_삭제는_남은_개수를_말한다():
    uid, cid = _course()
    text = _say(uid, cid, "마지막 빼줘")
    assert "뺐어요" in text and "2곳" in text


def test_추가는_추가된_장소를_말한다():
    uid, cid = _course()
    text = _say(uid, cid, "카페 하나 추가해줘")
    assert "추가했어요" in text and "4곳" in text
