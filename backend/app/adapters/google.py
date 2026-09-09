"""Google Places(v1) 어댑터 — 호출 종류를 요금 티어별로 분리한다.

과금 구조상 한 콜에 필드를 섞으면 가장 비싼 티어로 청구된다. 그래서 세 갈래로
나누고 절대 합치지 않는다.
  · `map_place_id`  — Text Search, 필드마스크 `places.id` 만 (IDs-only, 사실상 무료)
  · `fetch_hours`   — Place Details, 영업시간+영업상태만 (Pro, 월 5,000 무료)
  · `fetch_rating`  — Place Details, 평점+평가수만 (Enterprise, 월 1,000 무료)

영업시간은 30일, 평점은 90일 TTL 로 저장하고, 런타임에는 확정된 3~5곳의
만료분만 갱신한다(코스당 평균 2콜). 키가 없으면 전부 무동작.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from functools import lru_cache

import httpx

from app.config import settings
from app.schemas import Place

_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# 필드마스크. 티어가 다르므로 절대 한 콜에 합치지 않는다.
IDS_ONLY_MASK = "places.id"
HOURS_MASK = "regularOpeningHours,currentOpeningHours,businessStatus"
RATING_MASK = "rating,userRatingCount"

LOCATION_BIAS_M = 100.0  # 같은 이름의 다른 지점을 잡지 않도록 좁게
HOURS_TTL_DAYS = 30
RATING_TTL_DAYS = 90
MIN_RATING_COUNT = 30  # 평가 수가 이보다 적으면 평점을 신뢰하지 않는다
CLOSED_STATUSES = ("CLOSED_PERMANENTLY",)
# 일시 휴업도 그 날은 갈 수 없다 — 추천에서는 폐업과 같이 다룬다.
UNVISITABLE_STATUSES = ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY")


def _now() -> datetime:
    return datetime.now(UTC)


def _expired(checked_at: datetime | None, ttl_days: int) -> bool:
    if checked_at is None:
        return True
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    return _now() - checked_at >= timedelta(days=ttl_days)


def hours_stale(place: Place) -> bool:
    """영업시간을 다시 물어봐야 하는지(30일 TTL)."""
    return _expired(place.hours_checked_at, HOURS_TTL_DAYS)


def rating_stale(place: Place) -> bool:
    """평점을 다시 물어봐야 하는지(90일 TTL)."""
    return _expired(place.rating_checked_at, RATING_TTL_DAYS)


def _parse_hm(point: dict | None) -> time | None:
    if not point:
        return None
    hour, minute = point.get("hour"), point.get("minute", 0)
    if hour is None:
        return None
    return time(int(hour) % 24, int(minute or 0))


def _weekday_period(hours: dict | None, weekday: int) -> tuple[time | None, time | None]:
    """요일(월=0)의 첫 영업 구간. Google 은 일=0 기준이라 변환한다."""
    google_day = (weekday + 1) % 7
    for period in (hours or {}).get("periods") or []:
        if (period.get("open") or {}).get("day") == google_day:
            return _parse_hm(period.get("open")), _parse_hm(period.get("close"))
    return None, None


def has_periods(hours: dict | None) -> bool:
    """영업시간 정보가 아예 없는 것과, 있는데 그 요일만 없는 것을 구분하기 위한 것."""
    return bool((hours or {}).get("periods"))


def _consume(name: str) -> bool:
    """무료 한도가 남아 있으면 1콜을 차감하고 True. 소진되면 호출하지 않는다."""
    from app.quota import quota_store

    if not quota_store.allow(name):
        return False
    quota_store.record(name)
    return True


class GooglePlacesClient:
    """티어별로 분리된 Google Places 호출."""

    def __init__(self) -> None:
        self._key = settings.google_maps_api_key
        self._client = httpx.AsyncClient(timeout=10)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "X-Goog-Api-Key": self._key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }

    # --- ① 매핑 (IDs-only) -------------------------------------------------
    async def map_place_id(self, place: Place) -> str | None:
        """상호+좌표(100m 바이어스)로 Google place_id 만 받아온다."""
        if not self.enabled or not _consume("google.map_id"):
            return None
        body = {
            "textQuery": f"{place.name} {place.address or ''}".strip(),
            "languageCode": "ko",
            "maxResultCount": 1,
            "locationBias": {
                "circle": {
                    "center": {"latitude": place.lat, "longitude": place.lng},
                    "radius": LOCATION_BIAS_M,
                }
            },
        }
        resp = await self._client.post(
            _TEXT_SEARCH_URL, json=body, headers=self._headers(IDS_ONLY_MASK)
        )
        resp.raise_for_status()
        results = resp.json().get("places") or []
        return results[0].get("id") if results else None

    # --- ② 영업시간 (Pro) --------------------------------------------------
    async def fetch_hours(self, place_id: str) -> dict | None:
        """영업시간·영업상태만. 평점 필드를 절대 섞지 않는다."""
        if not self.enabled or not _consume("google.hours"):
            return None
        resp = await self._client.get(
            _DETAILS_URL.format(place_id=place_id), headers=self._headers(HOURS_MASK)
        )
        resp.raise_for_status()
        return resp.json()

    # --- ③ 평점 (Enterprise) ----------------------------------------------
    async def fetch_rating(self, place_id: str) -> tuple[float, int] | None:
        """집계 평점+평가 수만. 평가 수가 적으면 신호로 쓰지 않는다."""
        if not self.enabled or not _consume("google.rating"):
            return None
        resp = await self._client.get(
            _DETAILS_URL.format(place_id=place_id), headers=self._headers(RATING_MASK)
        )
        resp.raise_for_status()
        data = resp.json()
        rating = data.get("rating")
        count = int(data.get("userRatingCount") or 0)
        if rating is None or count < MIN_RATING_COUNT:
            return None
        return float(rating), count

    # --- 적용 --------------------------------------------------------------
    async def refresh_hours(self, place: Place, *, weekday: int | None = None) -> Place:
        """만료된 영업시간만 1콜로 갱신한다. 실패하면 '확인 필요'로 남긴다."""
        if not self.enabled or not hours_stale(place):
            return place
        from app.metrics import metrics_store

        try:
            place_id = place.google_place_id or await self.map_place_id(place)
            if not place_id:
                place.hours_unverified = True
                return place
            place.google_place_id = place_id
            data = await self.fetch_hours(place_id)
            metrics_store.record_external("google.hours", ok=True)
        except Exception:
            metrics_store.record_external("google.hours", ok=False)
            place.hours_unverified = True
            return place
        return self._apply_hours(place, data or {}, weekday)

    def _apply_hours(self, place: Place, data: dict, weekday: int | None) -> Place:
        place.business_status = data.get("businessStatus") or place.business_status
        hours = data.get("currentOpeningHours") or data.get("regularOpeningHours")
        day = _now().weekday() if weekday is None else weekday
        open_time, close_time = _weekday_period(hours, day)
        if open_time is not None:
            place.open_time = open_time
            place.close_time = close_time
            place.closed_that_day = False
            place.hours_unverified = False
        elif has_periods(hours):
            # 영업시간표는 있는데 그 요일 구간이 없다 = 정기휴무. "모름"이 아니다.
            place.closed_that_day = True
            place.hours_unverified = False
        else:
            # Google 에 영업시간이 없는 곳 → 상위에서 LLM 웹검색 폴백 + "확인 필요"
            place.hours_unverified = True
        place.hours_checked_at = _now()
        return place

    async def refresh_rating(self, place: Place) -> Place:
        """만료된 평점만 갱신(배치용). 런타임 코스 생성에서는 호출하지 않는다."""
        if not self.enabled or not rating_stale(place):
            return place
        from app.metrics import metrics_store

        try:
            place_id = place.google_place_id or await self.map_place_id(place)
            if not place_id:
                return place
            place.google_place_id = place_id
            result = await self.fetch_rating(place_id)
            metrics_store.record_external("google.rating", ok=True)
        except Exception:
            metrics_store.record_external("google.rating", ok=False)
            return place
        if result:
            place.rating, place.rating_count = result
        place.rating_checked_at = _now()
        return place


async def refresh_final_hours(
    places: list[Place], *, weekday: int | None = None
) -> list[Place]:
    """확정된 코스의 장소들만 TTL 확인 후 갱신(코스당 평균 2콜).

    후보 전체가 아니라 확정분에만 쓴다 — Pro 무료 한도(월 5,000)를 지키는 핵심.
    weekday 는 코스 날짜의 요일(월=0). 없으면 오늘 기준.
    """
    client = get_places_client()
    if not client.enabled or not places:
        return places
    targets = [p for p in places if hours_stale(p)]
    if not targets:
        return places
    await asyncio.gather(
        *(client.refresh_hours(p, weekday=weekday) for p in targets),
        return_exceptions=True,
    )
    return places


def is_permanently_closed(place: Place) -> bool:
    """Google 기준 영구 폐업. LOCALDATA 필터와 함께 이중으로 거른다."""
    return place.business_status in CLOSED_STATUSES


def is_closed_now(place: Place) -> bool:
    """그날 방문할 수 없는 상태(영구 폐업·일시 휴업·정기휴무)."""
    return place.business_status in UNVISITABLE_STATUSES or place.closed_that_day


@lru_cache(maxsize=1)
def get_places_client() -> GooglePlacesClient:
    """싱글턴. 매번 만들면 httpx 커넥션 풀이 재사용되지 않고 쌓인다."""
    return GooglePlacesClient()
