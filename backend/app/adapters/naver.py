"""Naver 지도/장소 어댑터 구현체.

- 장소 검색: 네이버 지역 검색 API (openapi.naver.com)
- 길찾기(차량): 네이버 클라우드 Directions 5 API

주의: 네이버 지역검색은 좌표를 KATECH(mapx/mapy, *1e7) 로 반환하므로 WGS84 변환이 필요하다.
walking 경로는 공식 제공이 제한적이라 직선거리 기반 근사로 대체한다.
호출 실패/키 미설정 시 상위(get_map_service)에서 Mock 으로 폴백한다.
"""
from __future__ import annotations

import math

import httpx

from app.config import settings
from app.schemas import Place, Route, TravelMode
from app.adapters.map_service import MapService

_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
_DIRECTIONS_URL = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"


class NaverMapService(MapService):
    def __init__(self) -> None:
        self._headers = {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
        }

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        query = " ".join([region, *keywords]).strip()
        # 네이버 지역검색 API 의 display 최대값은 5 (API 하드 제약)
        params = {"query": query, "display": min(limit, 5)}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_SEARCH_URL, params=params, headers=self._headers)
            resp.raise_for_status()
            items = resp.json().get("items", [])

        places: list[Place] = []
        for it in items:
            lat, lng = _katech_to_wgs84(it.get("mapx"), it.get("mapy"))
            name = _strip_tags(it.get("title", ""))
            address = it.get("roadAddress") or it.get("address") or ""
            places.append(
                Place(
                    id=_place_id(name, address),  # 장소 정체성 기반 안정 id
                    name=name,
                    category=it.get("category"),
                    address=address,
                    lat=lat,
                    lng=lng,
                    # 영업시간/브레이크는 지역검색 API 미제공 → 상세는 별도 소스 필요
                )
            )
        return places

    async def get_route(self, origin: Place, dest: Place, mode: TravelMode) -> Route:
        if mode == TravelMode.CAR:
            return await self._driving_route(origin, dest)
        return _straight_line_route(origin, dest, mode)

    async def _driving_route(self, origin: Place, dest: Place) -> Route:
        params = {
            "start": f"{origin.lng},{origin.lat}",
            "goal": f"{dest.lng},{dest.lat}",
        }
        headers = {
            "X-NCP-APIGW-API-KEY-ID": settings.naver_client_id,
            "X-NCP-APIGW-API-KEY": settings.naver_client_secret,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_DIRECTIONS_URL, params=params, headers=headers)
            resp.raise_for_status()
            summary = resp.json()["route"]["traoptimal"][0]["summary"]
        return Route(
            from_place_id=origin.id,
            to_place_id=dest.id,
            mode=TravelMode.CAR,
            duration_min=round(summary["duration"] / 60000),  # ms → 분
            distance_m=summary["distance"],
        )


def _strip_tags(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text)


def _place_id(name: str, address: str) -> str:
    """이름+주소 해시로 검색 반복에도 동일한 장소면 같은 id 를 갖게 한다."""
    import hashlib

    digest = hashlib.sha1(f"{name}|{address}".encode("utf-8")).hexdigest()[:12]
    return f"naver-{digest}"


def _katech_to_wgs84(mapx, mapy) -> tuple[float, float]:
    """네이버 지역검색 좌표(mapx/mapy, 문자열 *1e7)를 위경도로 변환."""
    try:
        lng = int(mapx) / 1e7
        lat = int(mapy) / 1e7
        return lat, lng
    except (TypeError, ValueError):
        return 0.0, 0.0


def _straight_line_route(origin: Place, dest: Place, mode: TravelMode) -> Route:
    """도보/대중교통 근사: 하버사인 직선거리 기반."""
    distance_m = _haversine_m(origin.lat, origin.lng, dest.lat, dest.lng)
    speed = {"walk": 67, "car": 500, "transit": 250}[mode.value]  # m/분
    return Route(
        from_place_id=origin.id,
        to_place_id=dest.id,
        mode=mode,
        duration_min=max(1, round(distance_m / speed)),
        distance_m=round(distance_m),
    )


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
