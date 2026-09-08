"""Google Places 어댑터 — 평점(정량 숫자) enrich.

네이버 지역검색은 평점을 제공하지 않으므로, 후보 장소를 Google Places 로 매칭해
평점(rating)·평점수(user_ratings_total)만 보강한다(요약 아님 → 약관 안전).
GOOGLE_MAPS_API_KEY 미설정/실패 시 보강을 건너뛰어 무영향(원본 유지).
"""
from __future__ import annotations

import asyncio

import httpx

from app.config import settings
from app.schemas import Place

_TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


class GooglePlacesEnricher:
    def __init__(self) -> None:
        self._key = settings.google_maps_api_key
        self._client = httpx.AsyncClient(timeout=10)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def enrich(self, places: list[Place]) -> list[Place]:
        """평점 없는 장소만 Google 평점으로 보강. 실패는 개별 무시(부분 보강)."""
        if not self.enabled or not places:
            return places
        # 이미 평점이 있는 장소까지 조회하면 호출 수·비용만 늘고 결과는 버려진다
        targets = [p for p in places if p.rating is None]
        if not targets:
            return places
        results = await asyncio.gather(
            *(self._rating_for(p) for p in targets), return_exceptions=True
        )
        from app.metrics import metrics_store

        for p, r in zip(targets, results, strict=False):
            if isinstance(r, tuple):
                p.rating = r[0]
                metrics_store.record_external("google.rating", ok=True)
            else:
                metrics_store.record_external("google.rating", ok=False)
        return places

    async def _rating_for(self, place: Place) -> tuple[float, int] | None:
        query = f"{place.name} {place.address or ''}".strip()
        params = {"query": query, "key": self._key, "language": "ko"}
        resp = await self._client.get(_TEXTSEARCH_URL, params=params)
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        top = results[0]
        rating = top.get("rating")
        if rating is None:
            return None
        return float(rating), int(top.get("user_ratings_total") or 0)


def get_places_enricher() -> GooglePlacesEnricher:
    return GooglePlacesEnricher()
