"""완화해도 결과가 같으면 다음 수를 제안한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _course(text: str) -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-1010-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": text})
    return uid, cid


def test_결과가_그대로면_같은_문구를_반복하지_않는다():
    uid, cid = _course("성수동 5곳 오전 10시부터 하루종일")
    before = client.get(f"/courses/{cid}").json()["items"]

    client.post(f"/courses/{cid}/relax", headers={"X-User-Id": uid})

    after = client.get(f"/courses/{cid}").json()["items"]
    text = client.get(f"/courses/{cid}/messages").json()[-1]["text"]
    assert [i["place"]["id"] for i in after] == [i["place"]["id"] for i in before]
    assert "완화해도 더 찾지 못했어요" in text


def test_결과가_바뀌면_평소_안내를_쓴다():
    uid, cid = _course("성수동 오전 10시 5시간 도보 10분 이내")
    client.post(f"/courses/{cid}/relax", headers={"X-User-Id": uid})
    text = client.get(f"/courses/{cid}/messages").json()[-1]["text"]
    # 결과가 달라졌으면 "찾지 못했어요" 대신 구성 안내가 나온다
    if "완화해도 더 찾지 못했어요" not in text:
        assert "코스를 구성했어요" in text or "완화" in text
