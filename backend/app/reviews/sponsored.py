"""협찬/체험단 리뷰 1차 필터링 (8장, 키워드/패턴 기반, 높은 신뢰도)."""
from __future__ import annotations

import re

# 법적 표기 의무 문구 위주 (실제 다수 포함되어 키워드 매칭만으로 상당수 탐지)
_SPONSORED_PATTERNS = [
    r"협찬",
    r"체험단",
    r"제공\s*받아",
    r"제공받은",
    r"원고료",
    r"소정의\s*(원고료|고료|대가)",
    r"무료로\s*제공",
    r"업체.{0,5}제공",
    r"대가를\s*받",
]

_COMPILED = [re.compile(p) for p in _SPONSORED_PATTERNS]


def is_sponsored(text: str) -> bool:
    """1차 필터: 표기 의무 문구가 포함되면 협찬으로 판단."""
    return any(p.search(text) for p in _COMPILED)


def matched_signals(text: str) -> list[str]:
    """탐지된 패턴 목록(디버깅/설명용)."""
    return [p.pattern for p in _COMPILED if p.search(text)]
