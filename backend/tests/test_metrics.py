from fastapi.testclient import TestClient

from app.main import app
from app.metrics import MetricsStore, metrics_store

client = TestClient(app)


def test_라우트_템플릿으로_집계된다():
    metrics_store.clear()
    cid = client.post("/courses").json()["id"]
    client.get(f"/courses/{cid}")
    client.get(f"/courses/{cid}")

    snap = client.get("/admin/metrics").json()
    routes = {r["route"] for r in snap["routes"]}
    # 코스 id 가 route 키에 섞이지 않는다
    assert "GET /courses/{course_id}" in routes
    assert not any(cid in r for r in routes)


def test_에러율과_백분위():
    store = MetricsStore()
    for ms in (10, 20, 30, 40):
        store.record("GET /x", 200, ms)
    store.record("GET /x", 500, 100)

    snap = store.snapshot()
    row = snap["routes"][0]
    assert row["count"] == 5
    assert row["errors"] == 1
    assert snap["error_rate"] == 0.2
    assert row["p50_ms"] <= row["p95_ms"]


def test_4xx는_에러율에_포함되지_않는다():
    store = MetricsStore()
    store.record("GET /x", 404, 5)
    snap = store.snapshot()
    assert snap["error_rate"] == 0.0
    assert snap["routes"][0]["client_errors"] == 1


def test_요청이_없으면_0():
    assert MetricsStore().snapshot() == {
        "total_requests": 0,
        "error_rate": 0.0,
        "routes": [],
        "externals": [],
    }
