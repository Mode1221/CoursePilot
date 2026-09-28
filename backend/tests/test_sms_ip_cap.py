"""한 IP 가 번호를 바꿔 가며 문자를 보내는 비용 공격 — IP 당 하루 상한."""
from fastapi.testclient import TestClient

from app.auth import MAX_SENDS_PER_IP_DAY, verification_store


def test_IP_당_하루_상한을_넘으면_429():
    from app.main import api

    c = TestClient(api)
    for i in range(MAX_SENDS_PER_IP_DAY):
        res = c.post("/auth/sms/request", json={"phone": f"010-4000-{i:04d}"})
        assert res.status_code == 200, res.text
    res = c.post("/auth/sms/request", json={"phone": "010-4000-9999"})
    assert res.status_code == 429


def test_다른_IP_는_따로_센다():
    for _ in range(MAX_SENDS_PER_IP_DAY):
        assert verification_store.can_send_from("1.1.1.1")
    assert not verification_store.can_send_from("1.1.1.1")
    assert verification_store.can_send_from("2.2.2.2")
    assert verification_store.can_send_from("")  # 주소 없는 내부 호출은 검사하지 않는다
