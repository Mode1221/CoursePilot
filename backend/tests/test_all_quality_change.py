"""코스 전체 성격 변경("전부 좀 더 저렴하게")은 조건 변경으로 다룬다."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import _ALL_QUALITY_RE, api

client = TestClient(api)
_phones = itertools.count(1)


@pytest.mark.parametrize(
    "text,matched",
    [
        ("전부 좀 더 저렴하게", True),
        ("다 조용한 데로 바꿔줘", True),
        ("모두 분위기 좋은 곳으로", True),
        ("두번째를 카페로 바꿔줘", False),
        ("첫번째 빼줘", False),
    ],
)
def test_전체_성격_변경을_가려낸다(text, matched):
    assert bool(_ALL_QUALITY_RE.search(text)) is matched


def _course() -> tuple[str, str]:
    uid = client.post("/signup", json={"phone": f"010-3131-{next(_phones):04d}"}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동에서 저녁 3곳"},
    )
    return uid, cid


def test_직전_조건을_유지한_채_다시_만든다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "전부 좀 더 저렴하게"},
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["region"] == "성수동"  # 지역 조건이 유지된다
    assert len(body["items"]) >= 2
