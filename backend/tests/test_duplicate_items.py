"""같은 장소를 두 번 담는 요청은 거절한다."""
from fastapi.testclient import TestClient

from app.main import api
from tests.helpers import owned_course

client = TestClient(api)
H: dict[str, str] = {}


def _course() -> str:
    uid, cid = owned_course(client)
    H["X-User-Id"] = uid
    return cid


def test_items_는_중복을_거절한다():
    cid = _course()
    res = client.post(f"/courses/{cid}/items", json={"place_ids": ["p1", "p1"]}, headers=H)
    assert res.status_code == 400


def test_reorder_도_중복을_거절한다():
    cid = _course()
    res = client.post(f"/courses/{cid}/reorder", json={"place_ids": ["p1", "p1"]}, headers=H)
    assert res.status_code == 400


def test_중복이_없으면_기존_동작():
    cid = _course()
    res = client.post(f"/courses/{cid}/items", json={"place_ids": []}, headers=H)
    assert res.status_code == 200
