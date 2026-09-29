"""민감한 값이 로그에 남지 않는다.

한 번 찍히면 그 로그를 보는 모든 사람과 로그 수집 시스템에 남는다.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.log_safe import mask_phone, mask_secret
from app.main import api

client = TestClient(api)

PHONE = "010-7788-9900"
DIGITS = "01077889900"


@pytest.mark.parametrize(
    "raw,expected",
    [("010-1234-5678", "010****5678"), ("01012345678", "010****5678"),
     ("", "(없음)"), (None, "(없음)"), ("123", "***")],
)
def test_전화번호는_뒤_네자리만_남긴다(raw, expected):
    assert mask_phone(raw) == expected


def test_비밀값은_길이만_남긴다():
    assert mask_secret("abcdef123456") == "***(12자)"
    assert mask_secret("") == "(미설정)"
    assert "abcdef" not in mask_secret("abcdef123456")


def _logged(caplog) -> str:
    """서비스가 남긴 로그만. (테스트 클라이언트인 httpx 자체 로그는 제외)"""
    return "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith("coursepilot")
    )


def test_인증_요청_로그에_번호와_코드가_없다(caplog):
    with caplog.at_level(logging.DEBUG):
        body = client.post("/auth/sms/request", json={"phone": PHONE}).json()
    text = _logged(caplog)
    assert DIGITS not in text and PHONE not in text
    code = body.get("dev_code")
    assert code and code not in text  # 개발 폴백 코드도 로그엔 남지 않는다


def test_가입_로그에_번호가_없다(caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/signup", json={"phone": PHONE})
    assert DIGITS not in _logged(caplog)


def test_관리_토큰이_로그에_남지_않는다(caplog, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "super-secret-admin-token")
    with caplog.at_level(logging.DEBUG):
        client.get("/admin/metrics", headers={"X-Admin-Token": "super-secret-admin-token"})
    assert "super-secret-admin-token" not in _logged(caplog)


def test_요청_로그는_쿼리스트링을_남기지_않는다(caplog):
    """검색어·토큰이 쿼리로 오면 경로만 남겨야 한다."""
    with caplog.at_level(logging.INFO):
        client.get("/places/search", params={"region": "성수동", "q": "secret-term"})
    assert "secret-term" not in _logged(caplog)
