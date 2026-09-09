"""주기 갱신 배치 — 원천별 갱신 주기가 다르므로 대상 집합도 다르게 잡는다.

  · 폐업·업력  : 주 1회, 저장된 전체(가장 싸다 — 무료 CSV)
  · 영업시간   : 30일 TTL, 최근 90일 내 추천된 '활성 집합'만
                 (90일간 한 번도 추천되지 않은 곳은 다시 등장할 때 즉석 갱신한다)
  · 평점       : 90일 TTL, 인기 상위만(Enterprise 무료 한도가 좁다)

활성 집합이 3,000~4,000개 수준이면 영업시간 갱신은 월 5,000 무료 한도 안에 든다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.batch.places_build import HOURS_PER_DAY, RATINGS_PER_DAY, fill_hours, fill_ratings
from app.schemas import Place

ACTIVE_WINDOW_DAYS = 90  # 이 기간 내 추천된 장소만 영업시간을 미리 갱신한다
SNAPSHOT_LIMIT = 20_000


@dataclass
class RefreshReport:
    scanned: int = 0
    active: int = 0
    closed_removed: int = 0
    longevity_filled: int = 0
    hours_filled: int = 0
    ratings_filled: int = 0


def is_active(place: Place, now: datetime | None = None) -> bool:
    """최근 90일 내에 코스로 추천된 적이 있는지."""
    seen = place.last_recommended_at
    if seen is None:
        return False
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) - seen < timedelta(days=ACTIVE_WINDOW_DAYS)


def refresh_closures(places: list[Place]) -> tuple[list[Place], int, int]:
    """폐업 제거 + 인허가일자 갱신. 반환: (남은 장소, 제거 수, 업력 채운 수)."""
    from app.adapters.localdata import get_localdata_registry

    registry = get_localdata_registry()
    registry.reload_if_stale()
    if not registry.loaded:
        return places, 0, 0
    kept: list[Place] = []
    filled = 0
    for place in places:
        record = registry.find(place.name, place.address)
        if record and record.closed:
            continue
        if record and record.opened_on and place.opened_on != record.opened_on:
            place.opened_on = record.opened_on
            filled += 1
        kept.append(place)
    return kept, len(places) - len(kept), filled


async def run(
    *,
    hours_limit: int = HOURS_PER_DAY,
    ratings_limit: int = RATINGS_PER_DAY,
    snapshot_limit: int = SNAPSHOT_LIMIT,
) -> RefreshReport:
    """하루 1회 실행 전제. 폐업은 전체, 유료 콜은 활성 집합에만."""
    from app.places import place_repo

    places = place_repo.all(limit=snapshot_limit)
    report = RefreshReport(scanned=len(places))
    kept, removed, filled = refresh_closures(places)
    report.closed_removed = removed
    report.longevity_filled = filled
    if removed:
        keep_ids = {p.id for p in kept}
        place_repo.delete_many([p.id for p in places if p.id not in keep_ids])

    active = [p for p in kept if is_active(p)]
    report.active = len(active)
    report.hours_filled = await fill_hours(active, hours_limit)
    report.ratings_filled = await fill_ratings(active, ratings_limit)
    if kept:
        place_repo.upsert_many(kept)
    return report


async def refresh_on_demand(places: list[Place]) -> list[Place]:
    """활성 집합 밖이라 미리 갱신하지 않은 장소가 다시 등장했을 때 즉석 갱신."""
    from app.adapters.google import refresh_final_hours

    return await refresh_final_hours(places)
