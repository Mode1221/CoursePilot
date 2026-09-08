from fastapi.testclient import TestClient

from app.feedback import FeedbackStore
from app.main import api


def test_feedback_store_counts():
    fs = FeedbackStore()
    fs.log("c1", "relax_offered")
    fs.log("c1", "relax_rejected")
    fs.log("c2", "relax_offered")
    assert fs.counts()["relax_offered"] == 2
    assert fs.counts("relax_rejected") == {"relax_rejected": 1}


def test_feedback_endpoint():
    client = TestClient(api)
    cid = client.post("/courses").json()["id"]
    assert client.post(f"/courses/{cid}/feedback", json={"kind": "relax_accepted"}).status_code == 200
    assert client.post("/courses/none/feedback", json={"kind": "x"}).status_code == 404


def test_인메모리는_이벤트를_쌓지_않고_집계만_한다():
    fs = FeedbackStore()
    for i in range(100):
        fs.log(f"c{i}", "relax_accepted")
    assert fs.counts() == {"relax_accepted": 100}
    assert len(fs._mem) == 1


def test_kind_로_거를_수_있다():
    fs = FeedbackStore()
    fs.log("c1", "liked")
    fs.log("c1", "disliked")
    assert fs.counts("liked") == {"liked": 1}
    assert fs.counts("nope") == {}
