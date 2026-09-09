"""협찬/체험단 리뷰 필터링 (8장 + docs/REVIEW_DATA_SOURCES.md).

다층 신호 점수화:
 1) 표기 문구(공정위 2024.12: 제목/첫문단 표기 의무 → 앞부분 가중)
 2) 구조 신호(과도한 해시태그/이모지, 쿠폰·예약·업체 연락처 삽입)
 3) 계정 패턴(특정 업체 반복) — 호출측에서 signal 로 주입

한계: 은닉(미표기) 협찬은 완전 탐지 불가. "명백 광고 제외 + 정량 우선"이 목표.
"""
from __future__ import annotations

import re

# 1) 법적 표기 의무 문구 (실제 다수 포함 → 키워드만으로 상당수 탐지)
_SPONSORED_PATTERNS = [
    r"협찬",
    r"체험단",
    r"제공\s*받아",
    r"제공받은",
    r"원고료",
    r"소정의\s*(원고료|고료|대가|수수료)",
    r"무료로\s*제공",
    r"업체.{0,5}제공",
    r"대가를\s*받",
    r"유료\s*광고",
    r"광고\s*포함",
    r"AD\b",
    # 실사용 표현 보강: 체험단·협찬의 다른 이름들
    r"서포터즈",
    r"앰배서더",
    r"앰버서더",
    r"인플루언서\s*마케팅",
    r"제작\s*지원",
    r"상품을?\s*제공",
    r"초대\s*받아",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _SPONSORED_PATTERNS]

# 2) 구조 신호(광고 글에 흔한 패턴)
_STRUCTURE_PATTERNS = [
    r"예약\s*문의",
    r"예약\s*링크",
    r"쿠폰",
    r"할인\s*코드",
    r"카톡\s*문의",
    r"DM\s*문의",
    r"공구",  # 공동구매
]
_STRUCTURE_COMPILED = [re.compile(p, re.IGNORECASE) for p in _STRUCTURE_PATTERNS]

# 3) 자비 방문임을 밝히는 표현(협찬 개연성을 낮추는 반대 신호)
_SELF_PAID_PATTERNS = [r"내돈내산", r"내\s*돈\s*주고", r"자비로\s*방문"]
_SELF_PAID_COMPILED = [re.compile(p, re.IGNORECASE) for p in _SELF_PAID_PATTERNS]

_FIRST_CHUNK = 120  # 제목/첫문단으로 간주할 앞부분 길이


def is_sponsored(text: str) -> bool:
    """1차 필터(불리언): 표기 의무 문구가 포함되면 협찬으로 판단."""
    return any(p.search(text) for p in _COMPILED)


def sponsored_score(text: str, account_repeat: bool = False) -> float:
    """협찬 개연성 0.0~1.0. 임계값(권장 0.5) 이상이면 제외 권장.

    account_repeat: 같은 업체/카테고리만 반복 게시하는 계정 신호(호출측 주입).
    """
    score = 0.0
    head = text[:_FIRST_CHUNK]

    # 표기 문구: 첫문단에 있으면 강한 신호(공정위 규제로 앞부분 표기 의무), 본문이면 약간
    if any(p.search(head) for p in _COMPILED):
        score += 0.7
    elif any(p.search(text) for p in _COMPILED):
        # 본문 어디든 표기 문구가 있으면 그 자체로 제외 대상(임계 0.5)
        score += 0.5

    # 구조 신호(누적, 상한)
    struct_hits = sum(1 for p in _STRUCTURE_COMPILED if p.search(text))
    score += min(0.3, struct_hits * 0.15)

    # 과도한 해시태그/이모지
    if len(re.findall(r"#\w+", text)) >= 8:
        score += 0.15

    if account_repeat:
        score += 0.2

    # "내돈내산"처럼 자비 방문을 밝히면 개연성을 낮춘다(표기 문구가 함께 있으면 상쇄만)
    if any(p.search(text) for p in _SELF_PAID_COMPILED):
        score -= 0.2

    return max(0.0, min(1.0, score))
