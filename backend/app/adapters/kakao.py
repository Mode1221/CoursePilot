"""Kakao 로컬 API 어댑터 — 장소 발견의 주 원천.

무료·무제한에 가깝고 좌표·카테고리 코드가 정확하다. 대신 평점·리뷰·영업시간은
주지 않으므로 그쪽은 Google(영업시간·평점)과 LOCALDATA(폐업·업력)가 맡는다.
경로는 네이버 Directions 가 맡으므로 여기서는 검색만 하고 라우팅은 위임한다.

크롤링(카카오맵 웹페이지)은 하지 않는다 — 공식 REST API 응답만 사용한다.
"""
from __future__ import annotations

import hashlib

import httpx

from app.adapters.map_service import MapService, MockMapService
from app.config import settings
from app.schemas import Place, Route, TravelMode

_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"

MAX_SIZE = 15  # 한 페이지 상한
MAX_PAGE = 3  # 키워드 검색은 45건이면 후보로 충분하다

# 카카오 category_group_code → 코스 슬롯. 이름 문자열 매칭보다 안정적이다.
GROUP_CODE_SLOT: dict[str, str] = {
    "FD6": "meal",  # 음식점 (술집도 여기 속해, 세부 카테고리명으로 다시 가른다)
    "CE7": "cafe",  # 카페
    "AT4": "activity",  # 관광명소
    "CT1": "activity",  # 문화시설
}

# 슬롯 → 카테고리 검색에 쓸 그룹 코드(배치 전수 수집용)
SLOT_GROUP_CODES: dict[str, tuple[str, ...]] = {
    "meal": ("FD6",),
    "cafe": ("CE7",),
    "bar": ("FD6",),  # 술집은 별도 코드가 없어 음식점에서 세부 카테고리로 추린다
    "activity": ("AT4", "CT1"),
}

# 음식점(FD6) 안에서 술집으로 봐야 하는 세부 카테고리 표기
BAR_CATEGORY_HINTS = ("술집", "호프", "요리주점", "포장마차", "바(BAR)", "와인", "칵테일", "이자카야")


def slot_for(group_code: str | None, category_name: str | None) -> str | None:
    """카카오 카테고리 → 코스 슬롯. 모르면 None(상위에서 이름 기반 분류)."""
    slot = GROUP_CODE_SLOT.get((group_code or "").upper())
    if slot == "meal" and any(h in (category_name or "") for h in BAR_CATEGORY_HINTS):
        return "bar"
    return slot


def _place_id(doc: dict) -> str:
    """카카오 문서 id 는 안정적이므로 그대로 접두사만 붙인다."""
    raw = doc.get("id")
    if raw:
        return f"kakao-{raw}"
    key = f"{doc.get('place_name')}|{doc.get('road_address_name')}"
    return f"kakao-{hashlib.sha1(key.encode()).hexdigest()[:12]}"


def to_place(doc: dict) -> Place | None:
    """카카오 응답 1건 → 정규화 Place. 좌표가 없으면 버린다."""
    try:
        lng, lat = float(doc["x"]), float(doc["y"])
    except (KeyError, TypeError, ValueError):
        return None
    return Place(
        id=_place_id(doc),
        name=doc.get("place_name") or "",
        category=doc.get("category_name") or None,
        category_code=doc.get("category_group_code") or None,
        address=doc.get("road_address_name") or doc.get("address_name") or None,
        lat=lat,
        lng=lng,
    )


class KakaoLocalService(MapService):
    """카카오 로컬 검색 + (경로는 위임)."""

    def __init__(self, route_service: MapService | None = None) -> None:
        self._headers = {"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"}
        self._client = httpx.AsyncClient(timeout=10)
        self._routes = route_service or MockMapService()

    @property
    def enabled(self) -> bool:
        return bool(settings.kakao_rest_api_key)

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        query = " ".join([region, *keywords]).strip()
        places: dict[str, Place] = {}
        for page in range(1, MAX_PAGE + 1):
            docs = await self._keyword_page(query, page)
            for doc in docs:
                place = to_place(doc)
                if place and place.id not in places:
                    places[place.id] = place
            if len(places) >= limit or len(docs) < MAX_SIZE:
                break
        return list(places.values())[:limit]

    async def _keyword_page(self, query: str, page: int) -> list[dict]:
        params = {"query": query, "size": MAX_SIZE, "page": page}
        resp = await self._client.get(_KEYWORD_URL, params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json().get("documents") or []

    async def search_category(
        self, group_code: str, lat: float, lng: float, radius_m: int = 1000, pages: int = MAX_PAGE
    ) -> list[Place]:
        """상권 좌표 기준 카테고리 전수 수집(초기 DB 구축 배치용)."""
        places: dict[str, Place] = {}
        for page in range(1, pages + 1):
            params = {
                "category_group_code": group_code,
                "x": lng,
                "y": lat,
                "radius": min(radius_m, 20000),
                "size": MAX_SIZE,
                "page": page,
                "sort": "distance",
            }
            resp = await self._client.get(_CATEGORY_URL, params=params, headers=self._headers)
            resp.raise_for_status()
            body = resp.json()
            for doc in body.get("documents") or []:
                place = to_place(doc)
                if place:
                    places.setdefault(place.id, place)
            if (body.get("meta") or {}).get("is_end", True):
                break
        return list(places.values())

    async def get_route(self, origin: Place, dest: Place, mode: TravelMode) -> Route:
        """카카오는 경로를 쓰지 않는다 — 네이버 Directions 등에 위임."""
        return await self._routes.get_route(origin, dest, mode)
