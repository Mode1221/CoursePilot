from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.api)


def _new_course(user_id: str) -> str:
    res = client.post("/courses", headers={"X-User-Id": user_id})
    return res.json()["id"]


def test_relax_requires_owner():
    course_id = _new_course("u1")
    assert client.post(f"/courses/{course_id}/relax").status_code == 403


def test_relax_without_previous_request():
    course_id = _new_course("u1")
    res = client.post(f"/courses/{course_id}/relax", headers={"X-User-Id": "u1"})
    assert res.status_code == 400


def test_relax_unknown_course():
    res = client.post("/courses/none/relax", headers={"X-User-Id": "u1"})
    assert res.status_code == 404
