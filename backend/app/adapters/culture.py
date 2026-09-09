"""공연·전시 일정 어댑터 — KOPIS(공연예술통합전산망) + 문화포털.

장소는 상시 영업이지만 공연·전시는 '기간'이 있다. 코스 날짜에 하는 것만
추천해야 하므로, 기간이 지난 전시가 후보에 남지 않도록 걸러낸다.
둘 다 공공데이터포털 키 하나로 쓰며, 키가 없으면 전부 무동작(폴백 유지).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.config import settings

_KOPIS_URL = "http://kopis.or.kr/openApi/restful/pblprfr"

_YMD = "%Y%m%d"


@dataclass(frozen=True)
class Performance:
    """한 공연·전시의 기간과 장소."""

    id: str
    title: str
    venue: str
    start: date
    end: date
    genre: str | None = None

    def runs_on(self, day: date) -> bool:
        return self.start <= day <= self.end


def parse_ymd(raw: str | None) -> date | None:
    """KOPIS 는 YYYY.MM.DD, 문화포털은 YYYYMMDD 로 준다."""
    text = (raw or "").strip().replace(".", "").replace("-", "").replace("/", "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime.strptime(text, _YMD).date()
    except ValueError:
        return None


def to_performance(item: dict) -> Performance | None:
    """KOPIS 공연 1건 → 정규화. 기간을 못 읽으면 버린다(날짜 검증이 불가능)."""
    start, end = parse_ymd(item.get("prfpdfrom")), parse_ymd(item.get("prfpdto"))
    if not start or not end or start > end:
        return None
    return Performance(
        id=str(item.get("mt20id") or ""),
        title=(item.get("prfnm") or "").strip(),
        venue=(item.get("fcltynm") or "").strip(),
        start=start,
        end=end,
        genre=(item.get("genrenm") or None),
    )


class CultureClient:
    """지역·기간으로 공연·전시를 찾는다."""

    def __init__(self) -> None:
        self._key = settings.tourapi_service_key  # 공공데이터포털 공통 키
        self._client = httpx.AsyncClient(timeout=10)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def performances(self, day: date, area_code: str = "11", rows: int = 50) -> list[Performance]:
        """해당 날짜에 실제로 진행 중인 공연·전시만 돌려준다(기본 지역: 서울)."""
        if not self.enabled:
            return []
        params = {
            "service": self._key,
            "stdate": day.strftime(_YMD),
            "eddate": day.strftime(_YMD),
            "cpage": 1,
            "rows": rows,
            "signgucode": area_code,
        }
        from app.metrics import metrics_store

        try:
            resp = await self._client.get(_KOPIS_URL, params=params)
            resp.raise_for_status()
            items = _xml_items(resp.text)
            metrics_store.record_external("kopis.performances", ok=True)
        except Exception:
            metrics_store.record_external("kopis.performances", ok=False)
            return []  # 일정 조회 실패는 코스 생성을 막지 않는다
        found = [to_performance(item) for item in items]
        return [p for p in found if p and p.runs_on(day)]


def _xml_items(xml_text: str) -> list[dict]:
    """KOPIS 는 XML 로만 응답한다. <db> 아래 자식 태그를 dict 로 편다."""
    from xml.etree import ElementTree

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    return [
        {child.tag: (child.text or "").strip() for child in db}
        for db in root.iter("db")
    ]


def drop_finished(performances: list[Performance], day: date) -> list[Performance]:
    """코스 날짜에 하지 않는 공연·전시를 후보에서 제거한다."""
    return [p for p in performances if p.runs_on(day)]


# 이 표기가 카테고리에 있으면 "기간이 있는 장소"로 보고 일정을 확인한다.
SCHEDULED_CATEGORY_HINTS = ("전시", "공연", "극장", "연극", "뮤지컬", "콘서트", "갤러리")


def needs_schedule_check(place) -> bool:
    """상시 영업이 아니라 기간제로 운영될 가능성이 있는 장소인지."""
    haystack = f"{place.category or ''} {place.name}"
    return any(hint in haystack for hint in SCHEDULED_CATEGORY_HINTS)


def _norm(text: str) -> str:
    return "".join((text or "").split()).lower()


def is_running(place, performances: list[Performance], day: date) -> bool:
    """그 장소에서 코스 날짜에 진행 중인 공연·전시가 있는지.

    일정 목록에 그 장소가 아예 없으면 판단하지 않는다(True) — KOPIS 에 없는
    소규모 전시장까지 "안 한다"고 잘라내면 후보가 과도하게 준다.
    """
    name = _norm(place.name)
    listed = [p for p in performances if _norm(p.venue) and _norm(p.venue) in name or name in _norm(p.venue)]
    if not listed:
        return True
    return any(p.runs_on(day) for p in listed)


async def drop_finished_places(places: list, day: date, client: CultureClient | None = None) -> list:
    """코스 날짜에 아무것도 하지 않는 공연·전시 장소를 뺀다."""
    client = client or CultureClient()
    targets = [p for p in places if needs_schedule_check(p)]
    if not client.enabled or not targets:
        return places
    performances = await client.performances(day)
    if not performances:
        return places  # 일정을 못 받으면 판단하지 않는다(폴백 유지)
    return [
        p
        for p in places
        if not needs_schedule_check(p) or is_running(p, performances, day)
    ]
