"""지도/장소 API 어댑터 레이어.

컨벤션: 벤더(Naver/Google 등)를 직접 호출하지 않고 반드시 이 인터페이스를 경유한다.
초기 구현체는 Naver 기준이나, 키가 없으면 개발용 Mock 구현체로 폴백한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import time
from functools import lru_cache
from time import monotonic

from app.config import settings
from app.constants import TRANSIT_OVERHEAD_MIN, TRAVEL_SPEED_M_PER_MIN
from app.schemas import Place, Route, TravelMode

SEARCH_CACHE_TTL_SEC = 300  # 장소 검색 결과 재사용 시간


class MapService(ABC):
    @abstractmethod
    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        """조건에 맞는 후보 장소 수집."""

    @abstractmethod
    async def get_route(
        self, origin: Place, dest: Place, mode: TravelMode
    ) -> Route:
        """두 장소 간 실제 이동 시간/거리 계산."""


# (카테고리, 개점, 마감). 밤 코스도 만들어볼 수 있도록 심야 영업(bar)을 섞는다.
_MOCK_KINDS = [
    ("restaurant", 11, 22),
    ("cafe", 10, 22),
    ("bar", 18, 2),
]


class MockMapService(MapService):
    """개발/테스트용. 결정론적 더미 데이터를 반환한다."""

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        base_lat, base_lng = 37.5445, 127.0557  # 성수동 근방
        places: list[Place] = []
        for i in range(limit):
            category, open_h, close_h = _MOCK_KINDS[i % len(_MOCK_KINDS)]
            places.append(
                Place(
                    id=f"mock-{region}-{i}",
                    name=f"{region} 장소 {i + 1}",
                    category=category,
                    address=f"{region} 어딘가 {i + 1}",
                    lat=base_lat + i * 0.001,
                    lng=base_lng + i * 0.001,
                    rating=4.0 + (i % 5) * 0.1,
                    price=10_000 + (i % 5) * 5_000,  # 1만~3만원
                    open_time=time(open_h, 0),
                    close_time=time(close_h, 0),
                    # 브레이크는 낮 영업 식당에만 (술집은 해당 없음)
                    break_start=time(15, 0) if category == "restaurant" and i % 3 == 0 else None,
                    break_end=time(17, 0) if category == "restaurant" and i % 3 == 0 else None,
                )
            )
        return places

    async def get_route(
        self, origin: Place, dest: Place, mode: TravelMode
    ) -> Route:
        # 위경도 차이를 대략적 거리/시간으로 환산 (개발용)
        dlat = abs(origin.lat - dest.lat)
        dlng = abs(origin.lng - dest.lng)
        distance_m = int((dlat + dlng) * 111_000)
        speed_m_per_min = TRAVEL_SPEED_M_PER_MIN[mode.value]
        duration_min = max(1, round(distance_m / speed_m_per_min))
        if mode is TravelMode.TRANSIT:
            duration_min += TRANSIT_OVERHEAD_MIN
        return Route(
            from_place_id=origin.id,
            to_place_id=dest.id,
            mode=mode,
            duration_min=duration_min,
            distance_m=distance_m,
        )


class SafeMapService(MapService):
    """실 구현체 호출 실패 시 Mock 으로 폴백하는 래퍼(파이프라인 무중단)."""

    def __init__(self, primary: MapService, fallback: MapService) -> None:
        self._primary = primary
        self._fallback = fallback

    async def search_places(self, region, keywords, limit=10):
        from app.metrics import metrics_store

        try:
            result = await self._primary.search_places(region, keywords, limit)
            if result:
                metrics_store.record_external("map.search_places", ok=True)
                return result
        except Exception:
            pass
        metrics_store.record_external("map.search_places", ok=False)
        return await self._fallback.search_places(region, keywords, limit)

    async def get_route(self, origin, dest, mode):
        from app.metrics import metrics_store

        try:
            route = await self._primary.get_route(origin, dest, mode)
            metrics_store.record_external("map.get_route", ok=True)
            return route
        except Exception:
            metrics_store.record_external("map.get_route", ok=False)
            return await self._fallback.get_route(origin, dest, mode)


class EnrichedMapService(MapService):
    """검색 결과에 Google Places 평점을 보강하는 데코레이터. 라우트는 위임."""

    def __init__(self, inner: MapService) -> None:
        self._inner = inner

    async def search_places(self, region, keywords, limit=10):
        places = await self._inner.search_places(region, keywords, limit)
        try:
            from app.adapters.google import get_places_enricher

            return await get_places_enricher().enrich(places)
        except Exception:
            return places  # 보강 실패는 무영향

    async def get_route(self, origin, dest, mode):
        return await self._inner.get_route(origin, dest, mode)


class CachedSearchMapService(MapService):
    """동일 조건 장소 검색·경로를 짧게 캐시하는 데코레이터(외부 호출·지연 절감).

    검색 결과는 몇 분 단위로 바뀌지 않으므로 TTL 안에서는 재사용한다.
    경로도 캐시한다 — Best-of-N 은 같은 장소 쌍의 경로를 시드마다 다시 묻기
    때문에, 캐시가 없으면 한 번의 코스 생성에서 같은 구간을 여러 번 조회한다.
    """

    def __init__(self, inner: MapService, ttl_sec: int = SEARCH_CACHE_TTL_SEC) -> None:
        self._inner = inner
        self._ttl = ttl_sec
        self._cache: dict[tuple[str, tuple[str, ...], int], tuple[float, list[Place]]] = {}
        self._routes: dict[tuple[str, str, str], tuple[float, Route]] = {}

    async def search_places(self, region, keywords, limit=10):
        key = (region, tuple(keywords), limit)
        now = monotonic()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self._ttl:
            return list(hit[1])
        places = await self._inner.search_places(region, keywords, limit)
        if places:
            self._sweep(now)
            self._cache[key] = (now, list(places))
        return places

    def _sweep(self, now: float) -> None:
        for key in [k for k, (ts, _) in self._cache.items() if now - ts >= self._ttl]:
            del self._cache[key]
        for key in [k for k, (ts, _) in self._routes.items() if now - ts >= self._ttl]:
            del self._routes[key]

    async def get_route(self, origin, dest, mode):
        key = (origin.id, dest.id, mode.value if hasattr(mode, "value") else str(mode))
        now = monotonic()
        hit = self._routes.get(key)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        route = await self._inner.get_route(origin, dest, mode)
        self._sweep(now)
        self._routes[key] = (now, route)
        return route


@lru_cache(maxsize=1)
def get_map_service() -> MapService:
    """설정에 따라 구현체 선택(싱글턴). 키 없으면 Mock, 있으면 Naver(+Mock 폴백).

    Google 키가 있으면 검색 결과에 평점을 보강한다.
    """
    if settings.map_provider == "naver" and settings.naver_client_id:
        from app.adapters.naver import NaverMapService

        base: MapService = SafeMapService(NaverMapService(), MockMapService())
    else:
        base = MockMapService()
    if settings.google_maps_api_key:
        base = EnrichedMapService(base)
    return CachedSearchMapService(base)
