"""영업시간을 모르는 장소를 어떻게 다룰지 — 점수 감점과 웹검색 보강 대상 선정의 단일 출처.

"영업시간 없음"은 두 가지가 섞여 있다.
- 아직 안 채운 곳(`hours_checked_at` 없음): 배치가 하루 할당량씩 채우는 중이라 인기 있는 곳도 비어 있다 → 건드리지 않는다.
- 확인했는데 없는 곳(`hours_unverified` + `open_time` 없음): Google·TourAPI 어디에도 없다.
  대개 덜 알려진 곳이라 **인기 신호가 없으면 점수를 깎아 뒤로 보낸다**(후보가 모자랄 때만 나온다).
  인기 신호가 있으면(요즘 뜨는 곳·팝업·블로그 언급 많음·우리 서비스 채택) 감점하지 않고,
  코스에 뽑혔을 때만 비싼 웹검색 보강(`adapters/hours_fallback.py`)을 쓴다.
공원·거리·산책로처럼 원래 영업시간이 없는 곳은 어느 쪽에도 해당하지 않는다.
"""
from __future__ import annotations

from app.schemas import Place

# 원래 영업시간이 없는 성격(이름·카테고리에 등장). 감점도, 웹검색도 하지 않는다.
NO_HOURS_KEYWORDS: tuple[str, ...] = (
    "공원", "거리", "광장", "산책", "둘레길", "한강", "해변", "호수", "숲", "골목", "산책로", "수변",
)
# 블로그 언급이 이만큼 있으면 알려진 곳으로 본다(awareness_signal 기준 약 0.7).
MIN_BLOG_MENTIONS = 300


def no_hours_kind(place: Place) -> bool:
    haystack = f"{place.category or ''} {place.name}"
    return any(k in haystack for k in NO_HOURS_KEYWORDS)


def hours_missing(place: Place) -> bool:
    """확인했는데도 영업시간이 없는 곳(원래 없는 성격 제외)."""
    return place.hours_unverified and place.open_time is None and not no_hours_kind(place)


def has_popularity(place: Place, popularity: float = 0.0) -> bool:
    """영업시간을 찾아볼 가치가 있을 만큼 알려진 곳인가."""
    return bool(
        (place.hot_score or 0) > 0
        or place.is_popup
        or (place.blog_mentions or 0) >= MIN_BLOG_MENTIONS
        or popularity > 0
    )
