"""초기 장소 DB 구축 파이프라인.

    상권 전수 수집(카카오) → 폐업 제거(LOCALDATA) → Google 매핑·영업시간·평점 → upsert

Google 콜은 무료 한도가 좁아 하루 단위로 페이싱한다(영업시간 160건/일, 평점은
상권별 상위 N건만). 한 번에 다 채우지 않고 여러 날에 걸쳐 채우는 것이 전제다.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.adapters.kakao import SLOT_GROUP_CODES, KakaoLocalService
from app.batch.districts import DISTRICTS, District
from app.schemas import Place

HOURS_PER_DAY = 160  # Google Pro 월 5,000 무료 → 배치 3,000, 런타임 2,000 분배 기준
RATINGS_PER_DAY = 11  # Enterprise 월 1,000 무료. 상권별 상위 100개를 3개월에 채운다
TOP_PER_DISTRICT = 100  # 평점을 물을 상권별 상위 개수

# 카테고리 검색에 쓸 그룹 코드(슬롯별 중복 제거)
GROUP_CODES = tuple(dict.fromkeys(c for codes in SLOT_GROUP_CODES.values() for c in codes))


@dataclass
class BuildReport:
    collected: int = 0
    closed_removed: int = 0
    hours_filled: int = 0
    ratings_filled: int = 0
    upserted: int = 0
    districts: list[str] = field(default_factory=list)


async def collect(
    kakao: KakaoLocalService, districts: tuple[District, ...] = DISTRICTS
) -> list[Place]:
    """상권×카테고리 전수 수집. 같은 장소는 한 번만."""
    found: dict[str, Place] = {}
    for district in districts:
        for code in GROUP_CODES:
            try:
                places = await kakao.search_category(
                    code, district.lat, district.lng, district.radius_m
                )
            except Exception:
                continue  # 한 상권 실패가 전체 배치를 멈추지 않는다
            for place in places:
                found.setdefault(place.id, place)
    return list(found.values())


def drop_closed(places: list[Place]) -> tuple[list[Place], int]:
    """LOCALDATA 로 폐업 제거 + 인허가일자(업력) 부착. 대장이 없으면 무동작."""
    from app.adapters.localdata import get_localdata_registry

    registry = get_localdata_registry()
    if not registry.loaded:
        return places, 0
    kept: list[Place] = []
    for place in places:
        record = registry.find(place.name, place.address)
        if record and record.closed:
            continue
        if record and record.opened_on:
            place.opened_on = record.opened_on
        kept.append(place)
    return kept, len(places) - len(kept)


async def fill_hours(places: list[Place], limit: int = HOURS_PER_DAY) -> int:
    """만료된 영업시간을 하루 할당량만큼 채운다(초과분은 다음 실행에서)."""
    from app.adapters.google import get_places_client, hours_stale

    client = get_places_client()
    if not client.enabled:
        return 0
    targets = [p for p in places if hours_stale(p)][:limit]
    if not targets:
        return 0
    await asyncio.gather(
        *(client.refresh_hours(p) for p in targets), return_exceptions=True
    )
    return sum(1 for p in targets if p.hours_checked_at is not None)


async def fill_ratings(
    places: list[Place], limit: int = RATINGS_PER_DAY, top_per_district: int = TOP_PER_DISTRICT
) -> int:
    """평점은 상권별 상위 장소에만 묻는다(Enterprise 월 1,000 한도).

    상위 기준은 아직 자체 신호(인기)뿐이라, 인기 순으로 자른다.
    """
    from app.adapters.google import get_places_client, rating_stale
    from app.popularity import popularity_store

    client = get_places_client()
    if not client.enabled:
        return 0
    scores = popularity_store.scores([p.id for p in places])
    ranked = sorted(places, key=lambda p: scores.get(p.id, 0.0), reverse=True)
    targets = [p for p in ranked[:top_per_district] if rating_stale(p)][:limit]
    if not targets:
        return 0
    await asyncio.gather(
        *(client.refresh_rating(p) for p in targets), return_exceptions=True
    )
    return sum(1 for p in targets if p.rating is not None)


async def run(
    districts: tuple[District, ...] = DISTRICTS,
    *,
    hours_limit: int = HOURS_PER_DAY,
    ratings_limit: int = RATINGS_PER_DAY,
    kakao: KakaoLocalService | None = None,
) -> BuildReport:
    """수집→필터→보강→저장 한 사이클. 매일 돌려 조금씩 채우는 것을 전제로 한다."""
    client = kakao or KakaoLocalService()
    report = BuildReport(districts=[d.name for d in districts])
    places = await collect(client, districts)
    report.collected = len(places)
    places, report.closed_removed = drop_closed(places)
    report.hours_filled = await fill_hours(places, hours_limit)
    report.ratings_filled = await fill_ratings(places, ratings_limit)
    if places:
        from app.places import place_repo

        place_repo.upsert_many(places)
        report.upserted = len(places)
    return report
