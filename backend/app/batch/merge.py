"""재수집분과 저장분 합치기.

배치는 매일 카카오에서 상권을 다시 훑는다. 그때 만들어지는 Place 는 이름·좌표·
카테고리뿐이고 보강 필드는 비어 있다. 그대로 덮어쓰면 어제 채운 영업시간·평점·
인지도·업력이 매일 지워지고, 하루 할당량(영업시간 160건)으로는 결코 다 채우지
못한다 — 실제로 그렇게 동작하고 있었다.

그래서 "이번에 값이 없으면 저장된 값을 그대로 둔다"로 합친다. 이 덕분에
Google 키가 나중에 들어와도 이미 채운 것은 건너뛰고 남은 것부터 이어서 채운다.
"""
from __future__ import annotations

from app.schemas import Place

# 카카오 재수집으로는 절대 채워지지 않는 필드들(다른 원천이 채운다).
# 새 값이 비어 있으면 저장된 값을 살린다.
ENRICHED_FIELDS: tuple[str, ...] = (
    "rating",
    "rating_count",
    "rating_checked_at",
    "google_place_id",
    "business_status",
    "hours_checked_at",
    "open_time",
    "close_time",
    "break_start",
    "break_end",
    "hours_unverified",
    "blog_mentions",
    "fact_tags",
    "caution_tags",
    "opened_on",
    "tour_listed",
    "price",
    "price_estimated",
    "last_recommended_at",
)

# 카카오가 매번 주는 값이라 최신으로 덮어써야 하는 필드는 여기에 없다
# (name/address/lat/lng/category/category_code — 가게 이전·개명을 반영해야 한다).


def _is_empty(value: object) -> bool:
    return value is None or value == [] or value is False


def merge_place(fresh: Place, stored: Place) -> Place:
    """새로 수집한 장소에 저장된 보강 값을 얹는다(새 값이 있으면 새 값 우선)."""
    for field in ENRICHED_FIELDS:
        if _is_empty(getattr(fresh, field)) and not _is_empty(getattr(stored, field)):
            setattr(fresh, field, getattr(stored, field))
    return fresh


def merge_with_stored(places: list[Place]) -> int:
    """저장소에서 같은 id 를 찾아 보강 값을 이어 붙인다. 살린 장소 수를 반환."""
    if not places:
        return 0
    from app.places import place_repo

    stored = place_repo.get_many([p.id for p in places])
    if not stored:
        return 0
    merged = 0
    for place in places:
        previous = stored.get(place.id)
        if previous is None:
            continue
        before = place.model_dump()
        merge_place(place, previous)
        if place.model_dump() != before:
            merged += 1
    return merged
