"""코스 항목 설정(undo 기반) + 장소 검색 엔드포인트."""
import pytest
from fastapi.testclient import TestClient

from app.main import api


@pytest.fixture
def client():
    return TestClient(api)


def _course_with_items(client) -> tuple[str, list[str]]:
    uid = client.post("/signup", json={"phone": "010-7777-0001"}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    items = client.get(f"/courses/{cid}").json()["items"]
    return cid, [it["place"]["id"] for it in items]


def test_search_returns_places_and_makes_them_addable(client):
    res = client.get("/places/search", params={"region": "성수동", "limit": 3})
    assert res.status_code == 200
    places = res.json()
    assert len(places) == 3

    # 검색 결과가 전역 저장소에 보관돼 곧바로 코스에 추가 가능해야 한다
    cid, _ = _course_with_items(client)
    added = client.post(f"/courses/{cid}/places", json={"place_id": places[0]["id"]})
    assert added.status_code in (200, 409)  # 이미 포함된 경우 409


def test_search_requires_region(client):
    assert client.get("/places/search", params={"region": "  "}).status_code == 400


def test_set_items_reorders_and_removes(client):
    cid, ids = _course_with_items(client)
    assert len(ids) >= 2
    target = list(reversed(ids))[:-1]  # 순서 뒤집고 하나 제거

    res = client.post(f"/courses/{cid}/items", json={"place_ids": target})
    assert res.status_code == 200
    assert [it["place"]["id"] for it in res.json()["items"]] == target


def test_set_items_restores_removed_place_for_undo(client):
    cid, ids = _course_with_items(client)
    kept = ids[:-1]
    client.post(f"/courses/{cid}/items", json={"place_ids": kept})

    # 되돌리기: 삭제된 장소를 포함한 원래 목록으로 복원 가능해야 한다
    res = client.post(f"/courses/{cid}/items", json={"place_ids": ids})
    assert res.status_code == 200
    assert [it["place"]["id"] for it in res.json()["items"]] == ids


def test_set_items_rejects_unknown_place(client):
    cid, ids = _course_with_items(client)
    res = client.post(f"/courses/{cid}/items", json={"place_ids": [*ids, "존재하지-않음"]})
    assert res.status_code == 404


def test_set_items_can_clear_course(client):
    cid, _ = _course_with_items(client)
    res = client.post(f"/courses/{cid}/items", json={"place_ids": []})
    assert res.status_code == 200
    assert res.json()["items"] == []
