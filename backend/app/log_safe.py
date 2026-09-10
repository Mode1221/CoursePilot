"""로그·응답에 남기면 안 되는 값을 가린다.

전화번호·인증번호·토큰·API 키가 로그에 한 번 찍히면 그 로그를 보는 모든 사람과
로그를 모으는 모든 시스템에 남는다. 값을 남길 일이 있으면 여기를 거친다.
"""
from __future__ import annotations

import re

_DIGITS = re.compile(r"\d")


def mask_phone(phone: str | None) -> str:
    """전화번호를 뒤 4자리만 남기고 가린다. 010-1234-5678 → 010****5678."""
    if not phone:
        return "(없음)"
    digits = _DIGITS.findall(phone)
    if len(digits) < 7:
        return "***"
    return f"{''.join(digits[:3])}****{''.join(digits[-4:])}"


def mask_secret(value: str | None) -> str:
    """토큰·API 키는 길이만 남긴다(있는지 없는지 확인용)."""
    if not value:
        return "(미설정)"
    return f"***({len(value)}자)"
