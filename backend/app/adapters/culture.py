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
        try:
            resp = await self._client.get(_KOPIS_URL, params=params)
            resp.raise_for_status()
            items = _xml_items(resp.text)
        except Exception:
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
