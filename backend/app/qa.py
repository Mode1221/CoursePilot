"""운영 QA(자동 점검) 요청 표시.

GitHub Actions 가 몇 시간마다 운영 사이트에서 실제 흐름(코스 만들기 → 상대 카드 → 자동 합치기 → 수락)을
돌린다. 그 요청들이 **학습 신호**(장소 인기·공동 채택·시간대·행동 선호·퍼널)를 쌓으면
하루 8번씩 같은 동네 같은 장소가 "인기"가 되어 실제 추천을 왜곡한다.

`X-QA-Token` 헤더가 설정값(QA_TOKEN)과 맞는 요청은 이 표시가 켜지고, 학습 스토어는 기록하지 않는다.
토큰이 비어 있으면(기본) QA 기능 전체가 꺼진다.
"""
from __future__ import annotations

import secrets
from contextvars import ContextVar

from app.config import settings

QA_PHONE = "qa:bot"  # 점검 전용 회원(전화·카카오 계정과 겹치지 않는 식별자)

_qa: ContextVar[bool] = ContextVar("coursepilot_qa", default=False)


def token_ok(token: str | None) -> bool:
    if not settings.qa_token or not token:
        return False
    return secrets.compare_digest(token.encode(), settings.qa_token.encode())


def mark(token: str | None) -> object:
    """요청 시작 때 부른다. 돌려준 값으로 `reset` 한다."""
    return _qa.set(token_ok(token))


def reset(handle: object) -> None:
    _qa.reset(handle)  # type: ignore[arg-type]


def learning_on() -> bool:
    """학습 신호를 기록해도 되는가(QA 요청이면 False)."""
    return not _qa.get()
