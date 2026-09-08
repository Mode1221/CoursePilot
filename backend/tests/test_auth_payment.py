from fastapi.testclient import TestClient

from app.auth import VerificationStore
from app.main import api


def test_sms_request_returns_dev_code_without_key():
    client = TestClient(api)
    res = client.post("/auth/sms/request", json={"phone": "010-1234-5678"})
    assert res.status_code == 200
    # SMS 키 미설정(개발) → 코드가 응답에 노출되어 자동화/테스트 가능
    assert res.json()["dev_code"] is not None


def test_sms_verify_flow():
    client = TestClient(api)
    code = client.post("/auth/sms/request", json={"phone": "010-9999-0000"}).json()["dev_code"]
    ok = client.post("/auth/sms/verify", json={"phone": "010-9999-0000", "code": code})
    assert ok.status_code == 200 and ok.json()["verified"] is True
    bad = client.post("/auth/sms/verify", json={"phone": "010-9999-0000", "code": "000000"})
    assert bad.status_code == 400  # 이미 소비됨/불일치


def test_verification_store_expiry(monkeypatch):

    vs = VerificationStore()
    code = vs.issue("p1")
    assert vs.verify("p1", code) is True
    assert vs.is_verified("p1") is True
    # 만료 위조
    vs._verified["p1"] = 0
    assert vs.is_verified("p1") is False


def test_signup_allowed_without_sms_when_disabled():
    client = TestClient(api)
    # sms_enabled=False(키 없음) → 인증 없이 가입 허용(개발/현행 동작 유지)
    res = client.post("/signup", json={"phone": "010-2222-3333"})
    assert res.status_code == 200


def test_purchase_dev_bypass_without_payment_key():
    client = TestClient(api)
    uid = client.post("/signup", json={"phone": "010-4444-5555"}).json()["user_id"]
    # 결제 비활성(키 없음) → imp_uid 없이도 지급(개발 폴백)
    res = client.post(f"/users/{uid}/purchase", json={"points": 3}, headers={"X-User-Id": uid})
    assert res.status_code == 200
    assert res.json()["questions_left"] >= 3


def test_코드를_여러_번_틀리면_폐기된다():
    from app.auth import MAX_ATTEMPTS, VerificationStore

    store = VerificationStore()
    code = store.issue("01099998888")
    for _ in range(MAX_ATTEMPTS):
        assert store.verify("01099998888", "000000") is False
    assert store.verify("01099998888", code) is False  # 폐기됨 → 재발급 필요
    assert store.verify("01099998888", store.issue("01099998888")) is True


def test_만료된_코드는_정리된다():
    from app.auth import VerificationStore

    store = VerificationStore()
    store.issue("01099997777")
    store._codes["01099997777"] = ("123456", 0.0)  # 만료 상태로 강제
    assert store.verify("01099997777", "123456") is False
    assert "01099997777" not in store._codes
