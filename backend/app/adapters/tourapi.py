"""TourAPI(한국관광공사) 어댑터 — 관광·문화시설의 영업시간·등재 여부.

Google Place Details 는 관광지·전시관에 영업시간이 없는 경우가 많다. 그 구멍을
공공 데이터로 메운다. 무료(공공데이터포털 키)이고, 등재 여부 자체가 "공식적으로
관리되는 장소"라는 약한 품질 신호가 된다.
"""
from __future__ import annotations

import re

import httpx

from app.config import settings
from app.schemas import Place

_SEARCH_URL = "https://apis.data.go.kr/B551011/KorService2/searchKeyword2"
_INTRO_URL = "https://apis.data.go.kr/B551011/KorService2/detailIntro2"

_COMMON = {"MobileOS": "ETC", "MobileApp": "CoursePilot", "_type": "json"}

# 관광타입: 12 관광지, 14 문화시설, 28 레포츠, 38 쇼핑, 39 음식점
CONTENT_TYPE_INTRO_FIELDS: dict[str, tuple[str, str]] = {
    "12": ("usetime", "restdate"),
    "14": ("usetimeculture", "restdateculture"),
    "28": ("usetimeleports", "restdateleports"),
    "38": ("opentime", "restdateshopping"),
    "39": ("opentimefood", "restdatefood"),
}

# "09:00 ~ 18:00", "09:00~18:00(입장마감 17:30)" 등에서 앞의 두 시각을 뽑는다.
_HOURS_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[~-]\s*(\d{1,2}):(\d{2})")


def _spans(text: str | None) -> list[tuple[str, str]]:
    """자유서술에서 시각 구간을 모두 뽑는다(잘못된 시각은 버린다)."""
    spans: list[tuple[str, str]] = []
    for match in _HOURS_RE.finditer(text or ""):
        oh, om, ch, cm = (int(g) for g in match.groups())
        if oh > 23 or ch > 24 or om > 59 or cm > 59:
            continue
        spans.append((f"{oh:02d}:{om:02d}", f"{ch % 24:02d}:{cm:02d}"))
    return spans


def parse_hours(text: str | None) -> tuple[str, str] | None:
    """자유서술 이용시간에서 '개장~마감'을 뽑는다. 못 뽑으면 None.

    "09:00~12:00, 13:00~18:00" 처럼 점심시간이 빠진 표기는 첫 구간만 보면
    오후 관람이 통째로 사라진다 → 첫 개장~마지막 마감으로 본다.
    """
    spans = _spans(text)
    if not spans:
        return None
    return spans[0][0], spans[-1][1]


def parse_break(text: str | None) -> tuple[str, str] | None:
    """구간이 둘로 나뉘어 있으면 그 사이가 쉬는 시간이다."""
    spans = _spans(text)
    if len(spans) < 2 or spans[0][1] >= spans[1][0]:
        return None
    return spans[0][1], spans[1][0]


class TourApiClient:
    """키워드로 관광 콘텐츠를 찾고, 소개정보에서 이용시간을 읽는다."""

    def __init__(self) -> None:
        self._key = settings.tourapi_service_key
        self._client = httpx.AsyncClient(timeout=10)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _params(self, **extra) -> dict:
        return {"serviceKey": self._key, **_COMMON, **extra}

    async def find(self, name: str) -> dict | None:
        """상호로 콘텐츠 1건을 찾는다(등재 여부 판정 겸용)."""
        if not self.enabled:
            return None
        resp = await self._client.get(
            _SEARCH_URL, params=self._params(keyword=name, numOfRows=1, pageNo=1)
        )
        resp.raise_for_status()
        items = _items(resp.json())
        return items[0] if items else None

    async def intro(self, content_id: str, content_type_id: str) -> dict | None:
        """소개정보(이용시간·휴무일)."""
        if not self.enabled:
            return None
        resp = await self._client.get(
            _INTRO_URL,
            params=self._params(contentId=content_id, contentTypeId=content_type_id),
        )
        resp.raise_for_status()
        items = _items(resp.json())
        return items[0] if items else None

    async def enrich(self, place: Place) -> Place:
        """Google 에 영업시간이 없는 관광·문화시설을 공공 데이터로 메운다."""
        from app.metrics import metrics_store

        try:
            item = await self.find(place.name)
            if not item:
                metrics_store.record_external("tourapi.enrich", ok=True)
                return place
            place.tour_listed = True
            content_type = str(item.get("contenttypeid") or "")
            intro = await self.intro(str(item.get("contentid")), content_type)
            metrics_store.record_external("tourapi.enrich", ok=True)
        except Exception:
            metrics_store.record_external("tourapi.enrich", ok=False)
            return place  # 보강 실패는 무영향
        fields = CONTENT_TYPE_INTRO_FIELDS.get(content_type)
        if not intro or not fields:
            return place
        raw = intro.get(fields[0])
        hours = parse_hours(raw)
        if hours:
            from datetime import time

            open_h, close_h = (time.fromisoformat(h) for h in hours)
            place.open_time, place.close_time = open_h, close_h
            rest = parse_break(raw)
            if rest:
                place.break_start, place.break_end = (time.fromisoformat(h) for h in rest)
            place.hours_unverified = False
        return place


def _items(body: dict) -> list[dict]:
    """TourAPI 응답의 items.item 은 단건일 때 dict, 다건일 때 list 로 온다."""
    items = (((body or {}).get("response") or {}).get("body") or {}).get("items")
    if not items or items == "":
        return []
    item = items.get("item") if isinstance(items, dict) else items
    if isinstance(item, dict):
        return [item]
    return list(item or [])
