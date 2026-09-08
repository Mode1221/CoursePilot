from fastapi.testclient import TestClient

import app.main as main


@main.api.get("/__boom")
async def _boom() -> dict:  # 테스트 전용 라우트
    raise RuntimeError("boom")


client = TestClient(main.api, raise_server_exceptions=False)


def test_unhandled_error_returns_friendly_payload():
    res = client.get("/__boom")
    assert res.status_code == 500
    body = res.json()
    assert "다시 시도" in body["detail"]
    assert body["request_id"]


def test_unhandled_error_carries_request_id_header():
    res = client.get("/__boom", headers={"X-Request-Id": "trace-1"})
    assert res.headers["X-Request-Id"] == "trace-1"
    assert res.json()["request_id"] == "trace-1"


def test_internal_details_are_not_leaked():
    assert "boom" not in client.get("/__boom").text
