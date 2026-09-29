"""저장된 장소로 검색을 대신하는 어댑터 — 키 없이 전체 흐름을 돌리기 위한 것.

키가 하나도 없으면 Mock 장소("성수동 장소 1")로 코스가 만들어진다. 그걸로는
이름·카테고리·영업시간·가격이 실제와 달라서 화면과 플래너를 제대로 못 본다.
시드(scripts/seed_mock_places.py)가 DB 에 넣어 둔 장소가 있으면 그걸 쓴다.

경로는 여전히 폴백(직선거리 근사)이다 — 검색만 대신한다.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from app.adapters.map_service import MapService, MockMapService
from app.batch.districts import DISTRICTS
from app.schemas import Place, Route, TravelMode

SEARCH_RADIUS_M = 3000  # 지역명을 못 찾았을 때 쓰는 기본 반경


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lng2 - lng1)
    x = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(x))


def _matches(place: Place, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{place.name} {place.category or ''}"
    return any(k and k in haystack for k in keywords)


def _round_robin(places: list[Place], limit: int) -> list[Place]:
    """슬롯별로 번갈아 뽑아 한 종류로 쏠리지 않게 한다."""
    from app.adapters.kakao import slot_for

    buckets: dict[str, list[Place]] = {}
    for place in places:
        buckets.setdefault(slot_for(place.category_code, place.category) or "기타", []).append(
            place
        )
    picked: list[Place] = []
    while len(picked) < limit and any(buckets.values()):
        for slot in list(buckets):
            if not buckets[slot]:
                continue
            picked.append(buckets[slot].pop(0))
            if len(picked) >= limit:
                break
    return picked


class SeededPlaceService(MapService):
    """저장소에 있는 장소 중 지역·키워드에 맞는 것을 돌려준다."""

    def __init__(self, route_service: MapService | None = None) -> None:
        self._routes = route_service or MockMapService()

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        from app.places import place_repo

        stored = place_repo.all(limit=100_000)
        if not stored:
            return []
        district = next((d for d in DISTRICTS if d.name and d.name in (region or "")), None)
        if district is not None:
            center = (district.lat, district.lng)
            radius = max(district.radius_m, 1500)
        else:
            # 모르는 지역이면 이름이 비슷한 장소를 우선하고, 없으면 전체에서 고른다
            named = [p for p in stored if region and region in (p.address or "")]
            pool = named or stored
            center = (pool[0].lat, pool[0].lng)
            radius = SEARCH_RADIUS_M

        near = [
            p for p in stored
            if _distance_m(center[0], center[1], p.lat, p.lng) <= radius
        ]
        if not near:
            near = stored
        matched = [p for p in near if _matches(p, keywords)]
        rest = [p for p in near if p not in matched]
        # 평가 수가 많은 곳을 앞에 둔다(플래너가 신호를 쓰는 것처럼 보이게)
        for group in (matched, rest):
            group.sort(key=lambda p: (p.rating_count or 0), reverse=True)
        # 한 카테고리로 쏠리면 코스 칸(밥·카페·술·볼거리)을 채우지 못한다 →
        # 슬롯을 번갈아 뽑아 골고루 섞는다.
        return _round_robin(matched + rest, limit)

    async def get_route(self, origin: Place, dest: Place, mode: TravelMode) -> Route:
        return await self._routes.get_route(origin, dest, mode)


def has_seed_places() -> bool:
    """시드로 넣은 장소가 저장소에 있는지."""
    from app.db import is_ready

    if not is_ready():
        return False
    from app.places import place_repo

    return any(p.is_mock for p in place_repo.all(limit=50))
