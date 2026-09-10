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


def test_같은_결제를_두_번_기록하면_두_번째는_거짓():
    # is_used 로 먼저 보지 않고 mark_used 반환값만으로 지급을 판단할 수 있어야 한다
    ledger = PaymentLedger()
    assert ledger.mark_used("imp_x", user_id="u1", points=5) is True
    assert ledger.mark_used("imp_x", user_id="u1", points=5) is False


def test_기록_선점당하면_지급하지_않는다(monkeypatch, _paid):
    """검증까지 통과해도 원장 기록에 실패하면(동시 요청이 먼저 선점) 409."""
    user_id = _signup()
    before = client.get(f"/users/{user_id}/credits", headers={"X-User-Id": user_id}).json()["questions_left"]
    monkeypatch.setattr(payment_ledger, "mark_used", lambda *a, **k: False)

    res = client.post(
        f"/users/{user_id}/purchase",
        json={"points": 3, "imp_uid": "imp_race"},
        headers={"X-User-Id": user_id},
    )
    assert res.status_code == 409
    assert client.get(f"/users/{user_id}/credits", headers={"X-User-Id": user_id}).json()["questions_left"] == before
