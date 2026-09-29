from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.api)


def test_response_carries_request_id():
    res = client.get("/health")
    assert res.headers.get("X-Request-Id")


def test_client_request_id_is_preserved():
    res = client.get("/health", headers={"X-Request-Id": "abc123"})
    assert res.headers["X-Request-Id"] == "abc123"
