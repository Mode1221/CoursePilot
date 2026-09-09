"""같은 결제로 반복 충전할 수 없다."""
import pytest
from fastapi.testclient import TestClient

from app.adapters.payment import PaymentResult
from app.main import api
from app.payment_ledger import PaymentLedger, payment_ledger

client = TestClient(api)


class _FakePay:
    async def verify(self, imp_uid: str) -> PaymentResult:
        return PaymentResult(paid=True, amount=1_000_000, status="paid")


@pytest.fixture
def _paid(monkeypatch):
    import app.adapters.payment as payment

    payment_ledger.clear()
    monkeypatch.setattr(payment, "get_payment_service", lambda: _FakePay())
    yield
    payment_ledger.clear()


def _signup() -> str:
    return client.post("/signup", json={"phone": "010-7777-1111"}).json()["user_id"]


def test_같은_imp_uid_는_한_번만_지급된다(_paid):
    uid = _signup()
    headers = {"X-User-Id": uid}
    body = {"points": 3, "imp_uid": "imp_dup"}
    first = client.post(f"/users/{uid}/purchase", json=body, headers=headers)
    second = client.post(f"/users/{uid}/purchase", json=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 409


def test_원장은_오래된_항목을_버린다():
    from app.payment_ledger import MAX_ENTRIES

    ledger = PaymentLedger()
    for i in range(MAX_ENTRIES + 5):
        ledger.mark_used(f"imp_{i}")
    assert ledger.is_used("imp_0") is False
    assert ledger.is_used(f"imp_{MAX_ENTRIES + 4}") is True


def test_결제키가_없어도_같은_결제로_반복_충전은_막힌다():
    """키 누락 배포에서도 리플레이만은 막는다(금액 검증은 결제사 조회가 필요)."""
    import itertools

    from fastapi.testclient import TestClient

    from app.main import api

    client = TestClient(api)
    phones = itertools.count(1)
    uid = client.post(
        "/signup", json={"phone": f"010-1414-{next(phones):04d}"}
    ).json()["user_id"]
    body = {"imp_uid": "imp_nokey_1", "amount": 5000, "points": 5}

    first = client.post(f"/users/{uid}/purchase", headers={"X-User-Id": uid}, json=body)
    assert first.status_code == 200
    again = client.post(f"/users/{uid}/purchase", headers={"X-User-Id": uid}, json=body)
    assert again.status_code == 409
    # 결제 식별자를 주지 않는 개발용 충전은 그대로 동작
    assert (
        client.post(
            f"/users/{uid}/purchase", headers={"X-User-Id": uid}, json={"points": 3}
        ).status_code
        == 200
    )
