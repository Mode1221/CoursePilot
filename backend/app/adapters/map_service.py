"""지도/장소 API 어댑터 레이어.

컨벤션: 벤더(Naver/Google 등)를 직접 호출하지 않고 반드시 이 인터페이스를 경유한다.
초기 구현체는 Naver 기준이나, 키가 없으면 개발용 Mock 구현체로 폴백한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import time

from app.config import settings
from app.schemas import Place, Route, TravelMode


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


class MockMapService(MapService):
    """개발/테스트용. 결정론적 더미 데이터를 반환한다."""

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        base_lat, base_lng = 37.5445, 127.0557  # 성수동 근방
        places: list[Place] = []
        for i in range(limit):
            places.append(
                Place(
                    id=f"mock-{region}-{i}",
                    name=f"{region} 장소 {i + 1}",
                    category="cafe" if i % 2 else "restaurant",
                    address=f"{region} 어딘가 {i + 1}",
                    lat=base_lat + i * 0.001,
                    lng=base_lng + i * 0.001,
                    rating=4.0 + (i % 5) * 0.1,
                    open_time=time(10, 0),
                    close_time=time(22, 0),
                    break_start=time(15, 0) if i % 3 == 0 else None,
                    break_end=time(17, 0) if i % 3 == 0 else None,
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
        speed_m_per_min = {"walk": 67, "car": 500, "transit": 250}[mode.value]
        duration_min = max(1, round(distance_m / speed_m_per_min))
        return Route(
            from_place_id=origin.id,
            to_place_id=dest.id,
            mode=mode,
            duration_min=duration_min,
            distance_m=distance_m,
        )


def get_map_service() -> MapService:
    """설정에 따라 구현체 선택. 키 없으면 Mock 폴백."""
    if settings.map_provider == "naver" and settings.naver_client_id:
        # TODO: NaverMapService 구현
        return MockMapService()
    return MockMapService()
