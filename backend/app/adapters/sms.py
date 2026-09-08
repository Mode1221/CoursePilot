"""SMS 발송 어댑터 (NHN Cloud SMS).

키 미설정 시 None → 상위(auth)에서 개발용 폴백(코드 로그/응답 노출).
"""
from __future__ import annotations

import httpx

from app.config import settings


class NhnCloudSms:
    def __init__(self) -> None:
        self._app_key = settings.nhn_sms_app_key
        self._secret = settings.nhn_sms_secret_key
        self._sender = settings.nhn_sms_sender

    async def send(self, phone: str, text: str) -> bool:
        url = (
            f"https://api-sms.cloud.toast.com/sms/v3.0/appKeys/{self._app_key}/sender/sms"
        )
        headers = {"Content-Type": "application/json", "X-Secret-Key": self._secret}
        body = {
            "body": text,
            "sendNo": self._sender,
            "recipientList": [{"recipientNo": phone.replace("-", "")}],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            header = resp.json().get("header", {})
            return bool(header.get("isSuccessful"))


def get_sms_service() -> NhnCloudSms | None:
    return NhnCloudSms() if settings.sms_enabled else None
