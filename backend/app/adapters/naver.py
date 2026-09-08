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

from app.adapters.map_service import MapService
from app.config import settings
from app.constants import TRANSIT_OVERHEAD_MIN, TRAVEL_SPEED_M_PER_MIN
from app.schemas import Place, Route, TravelMode

_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
_DIRECTIONS_URL = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"

MAX_DISPLAY = 5  # 네이버 지역검색 API 의 한 번 호출 상한
# 후보를 넓히기 위한 보조 질의어(코스 카테고리와 대응)
_FALLBACK_TERMS = ("맛집", "카페", "술집", "전시", "산책")


def _build_queries(region: str, keywords: list[str], limit: int) -> list[str]:
    """limit 을 채우기 위해 필요한 만큼의 검색 질의를 만든다."""
    base = " ".join([region, *keywords]).strip()
    queries = [base]
    if limit <= MAX_DISPLAY:
        return queries
    needed = -(-limit // MAX_DISPLAY) - 1  # 올림 나눗셈에서 기본 질의 1회를 뺀 나머지
    for term in _FALLBACK_TERMS[:needed]:
        queries.append(f"{base} {term}".strip())
    return queries


class NaverMapService(MapService):
    def __init__(self) -> None:
        self._headers = {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
        }
        # 요청 간 재사용하는 keep-alive 커넥션 풀
        self._client = httpx.AsyncClient(timeout=10)

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        # 지역검색 API 는 한 번에 5개까지만 준다(display 상한, start 도 무의미).
        # limit 이 더 크면 카테고리 보조어를 붙여 여러 번 질의하고 합친다.
        queries = _build_queries(region, keywords, limit)
        items: list[dict] = []
        seen_titles: set[str] = set()
        for query in queries:
            params = {"query": query, "display": MAX_DISPLAY}
            resp = await self._client.get(_SEARCH_URL, params=params, headers=self._headers)
            resp.raise_for_status()
            for it in resp.json().get("items", []):
                title = it.get("title", "")
                if title in seen_titles:
                    continue  # 질의가 겹쳐 같은 장소가 여러 번 오는 것을 막는다
                seen_titles.add(title)
                items.append(it)
            if len(items) >= limit:
                break
        items = items[:limit]

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
        resp = await self._client.get(_DIRECTIONS_URL, params=params, headers=headers)
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

    digest = hashlib.sha1(f"{name}|{address}".encode()).hexdigest()[:12]
    return f"naver-{digest}"


def _katech_to_wgs84(mapx, mapy) -> tuple[float, float]:
    """네이버 지역검색 좌표(mapx/mapy, 문자열 *1e7)를 위경도로 변환."""
    try:
        lng = int(mapx) / 1e7
        lat = int(mapy) / 1e7
        return lat, lng
    except (TypeError, ValueError):
        return 0.0, 0.0


# 실제 길은 직선이 아니다(블록·횡단보도 우회). 도시 보행 기준 통용되는 계수.
DETOUR_FACTOR = 1.3


def _straight_line_route(origin: Place, dest: Place, mode: TravelMode) -> Route:
    """도보/대중교통 근사: 하버사인 직선거리에 우회 계수를 곱해 보정."""
    distance_m = _haversine_m(origin.lat, origin.lng, dest.lat, dest.lng) * DETOUR_FACTOR
    speed = TRAVEL_SPEED_M_PER_MIN[mode.value]  # m/분
    duration_min = max(1, round(distance_m / speed))
    if mode is TravelMode.TRANSIT:
        duration_min += TRANSIT_OVERHEAD_MIN  # 대기·환승 고정 비용
    return Route(
        from_place_id=origin.id,
        to_place_id=dest.id,
        mode=mode,
        duration_min=duration_min,
        distance_m=round(distance_m),
    )


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
