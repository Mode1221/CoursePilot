"""결제 검증 어댑터 (포트원/아임포트 v1).

imp_uid 로 실제 결제를 조회해 상태(paid)·금액을 검증한다.
키 미설정 시 None → 상위(main)에서 개발용 폴백(검증 생략).
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings


def _client() -> httpx.AsyncClient:
    """HTTP 클라이언트 팩토리. 테스트가 고정 응답 전송 계층으로 갈아끼운다."""
    return httpx.AsyncClient(timeout=10)


_TOKEN_URL = "https://api.iamport.kr/users/getToken"
_PAYMENT_URL = "https://api.iamport.kr/payments/{imp_uid}"


@dataclass
class PaymentResult:
    paid: bool
    amount: int
    status: str


class PortOneClient:
    def __init__(self) -> None:
        self._key = settings.portone_api_key
        self._secret = settings.portone_api_secret

    async def verify(self, imp_uid: str) -> PaymentResult:
        async with _client() as client:
            tok = await client.post(
                _TOKEN_URL,
                json={"imp_key": self._key, "imp_secret": self._secret},
            )
            tok.raise_for_status()
            token = tok.json()["response"]["access_token"]
            pay = await client.get(
                _PAYMENT_URL.format(imp_uid=imp_uid),
                headers={"Authorization": token},
            )
            pay.raise_for_status()
            r = pay.json()["response"]
        return PaymentResult(
            paid=r.get("status") == "paid",
            amount=int(r.get("amount") or 0),
            status=r.get("status", "unknown"),
        )


def get_payment_service() -> PortOneClient | None:
    return PortOneClient() if settings.payment_enabled else None
