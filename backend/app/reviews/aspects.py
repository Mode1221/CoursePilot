"""리뷰 애스펙트 추출 (8장).

LLM 키가 없거나 호출이 실패해도 UI가 비지 않도록, 리뷰 문장에서 규칙 기반으로
'좋은 점 / 주의할 점' 태그를 뽑는다. 리뷰 원문 인용 없이 태그만 노출해 약관 안전.
"""
from __future__ import annotations

import re

# 태그 → (긍정 패턴, 부정 패턴). 같은 축(예: 대기)에 대해 양방향을 함께 본다.
_ASPECTS: list[tuple[str, str, str]] = [
    # (태그, 긍정 정규식, 부정 정규식)
    ("웨이팅", r"웨이팅\s*없|바로\s*입장|줄\s*안\s*서", r"웨이팅|줄\s*(이|을)?\s*(길|서)|대기\s*\d+"),
    ("주차", r"주차\s*(장)?\s*(넉넉|편|가능|무료)", r"주차\s*(불가|어렵|힘들|협소|자리\s*없)"),
    ("분위기", r"분위기\s*(좋|최고|예쁘)|뷰\s*(좋|맛집)|인테리어\s*(예쁘|좋)", r"분위기\s*(별로|아쉽)"),
    ("소음", r"조용|한적|차분", r"시끄|소란|웅성"),
    ("가성비", r"가성비|가격\s*(착|저렴)|합리적", r"비싸|가격\s*대비\s*아쉽|바가지"),
    ("친절", r"친절|응대\s*(좋|훌륭)", r"불친절|응대\s*(별로|나쁨)"),
    ("맛", r"맛(있|집)|존맛|훌륭", r"맛\s*(없|별로)|싱겁|짜"),
    ("청결", r"깨끗|청결|위생\s*좋", r"더럽|지저분|위생\s*(별로|안)"),
    ("좌석", r"자리\s*(넉넉|많)|넓(고|은)?\s*(공간|매장)?", r"좁|자리\s*(없|부족)|협소"),
    # 실사용에서 자주 갈리는 축 보강
    ("콘센트", r"콘센트\s*(많|있)|충전\s*가능|카공", r"콘센트\s*(없|부족)|노트북\s*(금지|불가)"),
    ("예약", r"예약\s*(가능|쉬|편)|워크인\s*가능", r"예약\s*(필수|어렵|안\s*됨|불가)"),
    ("양", r"양\s*(많|푸짐)|푸짐", r"양\s*(적|아쉽)|부족한\s*양"),
]

MIN_HITS = 1  # 최소 언급 횟수(리뷰가 적을 때의 하한)
MENTION_RATIO = 0.2  # 리뷰 수 대비 이 비율 이상 언급돼야 태그로 인정(1건 잡음 억제)


def _threshold(review_count: int) -> int:
    """리뷰가 많을수록 더 많이 언급된 축만 남긴다."""
    return max(MIN_HITS, round(review_count * MENTION_RATIO))


def extract_aspects(reviews: list[str]) -> tuple[list[str], list[str]]:
    """(좋은 점, 주의할 점) 태그 목록. 언급 빈도 내림차순, 각 최대 4개.

    한 태그가 양쪽 모두 걸리면 더 많이 언급된 쪽만 남긴다(모순 방지).
    """
    text = "\n".join(reviews)
    need = _threshold(len(reviews))
    pros: dict[str, int] = {}
    cons: dict[str, int] = {}
    for tag, pos, neg in _ASPECTS:
        p = len(re.findall(pos, text))
        n = len(re.findall(neg, text))
        if p >= need and p > n:
            pros[tag] = p
        elif n >= need and n > p:
            cons[tag] = n
    return _top(pros), _top(cons)


def _top(counts: dict[str, int], limit: int = 4) -> list[str]:
    return [tag for tag, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:limit]
