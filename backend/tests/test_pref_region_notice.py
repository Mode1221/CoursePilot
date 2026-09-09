"""선호 지역으로 코스를 만들면 그 사실을 알린다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _user_with_region(region: str) -> str:
    uid = client.post(
        "/signup", json={"phone": f"010-3838-{next(_phones):04d}"}
    ).json()["user_id"]
    client.put(
        f"/users/{uid}/preferences",
        headers={"X-User-Id": uid},
        json={"region": region, "diet": []},
    )
    return uid


def _reply(uid: str, text: str) -> str:
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": text})
    return client.get(f"/courses/{cid}/messages").json()[-1]["text"]


def test_지역을_말하지_않으면_선호_지역을_알린다():
    uid = _user_with_region("연남동")
    assert "설정하신 연남동 기준" in _reply(uid, "저녁 7시에 놀 데 찾아줘")


def test_문장에_지역이_있으면_알리지_않는다():
    uid = _user_with_region("연남동")
    assert "설정하신" not in _reply(uid, "성수동에서 저녁 7시")


def test_선호_지역이_없으면_기존_안내():
    uid = client.post(
        "/signup", json={"phone": f"010-3939-{next(_phones):04d}"}
    ).json()["user_id"]
    text = _reply(uid, "저녁 7시에 놀 데 찾아줘")
    assert "설정하신" not in text
    assert "못 알아들어" in text  # 지역 추측 안내는 그대로
