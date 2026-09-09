"""편집 명령이 아무것도 바꾸지 못하면 그 사실을 알린다."""
import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _course_with_items() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-3333-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return cid, uid


def test_없는_순번을_지목하면_안내한다():
    cid, uid = _course_with_items()
    before = client.get(f"/courses/{cid}").json()["items"]
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "9번째 삭제해줘"}
    )
    messages = client.get(f"/courses/{cid}/messages").json()
    assert "찾지 못했어요" in messages[-1]["text"]
    assert client.get(f"/courses/{cid}").json()["items"] == before


def test_정상_편집은_안내하지_않는다():
    cid, uid = _course_with_items()
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "1번째 삭제해줘"}
    )
    messages = client.get(f"/courses/{cid}/messages").json()
    assert "찾지 못했어요" not in messages[-1]["text"]


def test_반영되지_않으면_크레딧을_돌려준다():
    cid, uid = _course_with_items()
    before = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()["questions_left"]
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "9번째 삭제해줘"}
    )
    after = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()["questions_left"]
    assert after == before
