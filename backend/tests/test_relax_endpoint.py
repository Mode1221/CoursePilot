from fastapi.testclient import TestClient

import app.main as main
from tests.helpers import owned_course

client = TestClient(main.api)


def test_relax_requires_owner():
    _, course_id = owned_course(client)
    assert client.post(f"/courses/{course_id}/relax").status_code == 403


def test_relax_without_previous_request():
    uid, course_id = owned_course(client)
    res = client.post(f"/courses/{course_id}/relax", headers={"X-User-Id": uid})
    assert res.status_code == 400


def test_relax_unknown_course():
    res = client.post("/courses/none/relax", headers={"X-User-Id": "u1"})
    assert res.status_code == 404
