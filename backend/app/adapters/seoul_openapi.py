"""서울 열린데이터광장 — 실시간 도시데이터(동네 혼잡도·주변 행사)와 문화행사 정보.

키: SEOUL_OPENAPI_KEY. 응답 필드는 스모크(scripts/smoke_seoul.py)로 확인한다 — 필드가 달라도
죽지 않게 방어적으로 읽는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE = "http://openapi.seoul.go.kr:8088"

# 우리 상권 → 서울 실시간 도시데이터 장소명(공식 120곳 목록 기준, 스모크로 검증)
CITYDATA_AREA: dict[str, str | tuple[str, ...]] = {
    "성수": "성수카페거리",
    "홍대": "홍대 관광특구",
    "연남": "연남동",
    "합정": "합정역",
    "망원": "망원한강공원",
    "이태원": "이태원 관광특구",
    "한남": "이태원 관광특구",
    "강남역": "강남역",
    "신사": "가로수길",
    "압구정": "압구정로데오거리",
    "잠실": "잠실 관광특구",
    "송리단길": "잠실 관광특구",
    "여의도": "여의도",
    # 실측: 을지로3가역·을지로입구역·을지로4가역·을지로 모두 공식 목록에 없음 → 가장 가까운 공식 지점으로.
    # 화면엔 실제 조회한 지점 이름("명동 관광특구")이 그대로 나간다.
    "을지로": ("명동 관광특구", "종로·청계 관광특구"),
    "종로": "종로·청계 관광특구",
    "익선동": "익선동",
    "삼청동": "북촌한옥마을",
    "명동": "명동 관광특구",
    "서촌": "경복궁",
    "건대": "건대입구역",
    "신촌": "신촌·이대역",
    "혜화": "혜화역",
    "용산": "용산역",
    "문래": "영등포 타임스퀘어",
}

CONGESTION_ORDER = ("여유", "보통", "약간 붐빔", "붐빔")


@dataclass
class AreaStatus:
    area: str
    level: str | None = None  # 여유·보통·약간 붐빔·붐빔
    message: str | None = None
    calmer_hour: str | None = None  # 앞으로 12시간 중 가장 한산한 시각("17시")
    events: list[dict] = field(default_factory=list)  # {name, place, period, lat, lng, url}


def _key() -> str | None:
    return settings.seoul_openapi_key or None


def parse_citydata(body: dict, area: str) -> AreaStatus:
    """실시간 도시데이터 응답 → 혼잡도·한산한 시각·주변 행사."""
    st = AreaStatus(area=area)
    city = body.get("CITYDATA") or body.get("citydata") or {}
    live = city.get("LIVE_PPLTN_STTS") or []
    if isinstance(live, dict):
        live = [live]
    if live:
        row = live[0]
        st.level = row.get("AREA_CONGEST_LVL")
        st.message = row.get("AREA_CONGEST_MSG")
        fcst = row.get("FCST_PPLTN") or []
        ranked = [
            (CONGESTION_ORDER.index(f.get("FCST_CONGEST_LVL")), f.get("FCST_TIME", ""))
            for f in fcst
            if f.get("FCST_CONGEST_LVL") in CONGESTION_ORDER
        ]
        if ranked:
            lvl, t = min(ranked)
            if st.level in CONGESTION_ORDER and lvl < CONGESTION_ORDER.index(st.level):
                st.calmer_hour = _hour(t)
    for ev in city.get("EVENT_STTS") or []:
        try:
            st.events.append(
                {
                    "name": ev.get("EVENT_NM"),
                    "place": ev.get("EVENT_PLACE"),
                    "period": ev.get("EVENT_PERIOD"),
                    "lat": float(ev.get("EVENT_Y")) if ev.get("EVENT_Y") else None,
                    "lng": float(ev.get("EVENT_X")) if ev.get("EVENT_X") else None,
                    "url": ev.get("URL"),
                }
            )
        except (TypeError, ValueError):
            continue
    return st


def _hour(raw: str) -> str | None:
    try:
        return f"{datetime.strptime(raw[:16], '%Y-%m-%d %H:%M').hour}시"
    except (ValueError, TypeError):
        return None


_RESOLVED: dict[str, str] = {}  # 상권 → 실제로 응답한 공식 장소명(후보가 여러 개일 때)


async def area_status(client: httpx.AsyncClient, region: str) -> AreaStatus | None:
    key = _key()
    names = CITYDATA_AREA.get(region)
    if not key or not names:
        return None
    candidates = [_RESOLVED[region]] if region in _RESOLVED else ([names] if isinstance(names, str) else list(names))
    for area in candidates:
        try:
            resp = await client.get(f"{BASE}/{key}/json/citydata/1/5/{area}")
            resp.raise_for_status()
            st = parse_citydata(resp.json(), area)
        except Exception as exc:
            logger.warning("citydata 실패(%s): %s", area, exc)
            continue
        if st.level:
            _RESOLVED[region] = area
            return st
    return None


# 데이트 할거리로 쓸 분야(CODENAME 앞부분). 교육/체험은 도서관·주민센터 프로그램이 대부분이라 뺀다(실측).
DATE_KINDS = ("전시", "미술", "콘서트", "클래식", "뮤지컬", "오페라", "연극", "국악", "무용", "축제", "독주", "독창", "영화")
NOT_FOR_DATES = (
    "도서관", "주민센터", "행정복지센터", "복지관", "구민회관", "평생학습", "강연", "강좌", "강의", "세미나",
    "북토크", "사서", "어린이", "유아", "키즈", "초등", "청소년", "학부모", "시니어", "어르신",
    "인문학", "지혜학교", "아카데미", "교실", "수업", "공모", "모집",
)


def is_date_worthy(kind: str | None, title: str | None, place: str | None) -> bool:
    k = kind or ""
    if not any(w in k for w in DATE_KINDS):
        return False
    return is_date_worthy_text(title, place)


def is_date_worthy_text(title: str | None, place: str | None) -> bool:
    """분야 정보가 없는 행사(도시데이터 주변 행사)용 — 제목·장소만으로 거른다."""
    hay = f"{title or ''} {place or ''}"
    return not any(w in hay for w in NOT_FOR_DATES)


def period_end(raw: str | None) -> str | None:
    """'2026-09-01~2026-10-01' 같은 기간 문자열 → 종료일 ISO. 못 읽으면 None."""
    if not raw:
        return None
    import re

    dates = re.findall(r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})", str(raw))
    if not dates:
        return None
    y, m, d = dates[-1]
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_cultural_events(body: dict, on: date) -> list[dict]:
    """문화행사 정보 → 그날 진행 중인 전시·공연·축제(좌표 있고 데이트에 맞는 것만)."""
    rows = (body.get("culturalEventInfo") or {}).get("row") or []
    out = []
    for r in rows:
        if not is_date_worthy(r.get("CODENAME"), r.get("TITLE"), r.get("PLACE")):
            continue
        try:
            start = _d(r.get("STRTDATE"))
            end = _d(r.get("END_DATE"))
            if start and end and not (start <= on <= end):
                continue
            lat, lng = float(r.get("LAT") or 0), float(r.get("LOT") or 0)
            # 좌표 열 이름이 바뀐 적이 있다 — 서울 범위를 벗어나면 뒤집어 본다
            if not (37.0 < lat < 38.0) and 37.0 < lng < 38.0:
                lat, lng = lng, lat
            if not (37.0 < lat < 38.0 and 126.0 < lng < 128.0):
                continue
            out.append(
                {
                    "name": r.get("TITLE"),
                    "kind": r.get("CODENAME"),
                    "place": r.get("PLACE"),
                    "gu": r.get("GUNAME"),
                    "fee": r.get("USE_FEE"),
                    "is_free": (r.get("IS_FREE") == "무료") or ("무료" in (r.get("USE_FEE") or "")),
                    "start": start.isoformat() if start else None,
                    "end": end.isoformat() if end else None,
                    "lat": lat,
                    "lng": lng,
                    "url": r.get("ORG_LINK") or r.get("HMPG_ADDR"),
                }
            )
        except (TypeError, ValueError):
            continue
    return out


def _d(raw) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


async def cultural_events(client: httpx.AsyncClient, on: date, pages: int = 3) -> list[dict]:
    key = _key()
    if not key:
        return []
    out: list[dict] = []
    for p in range(pages):
        a, b = p * 1000 + 1, (p + 1) * 1000
        try:
            resp = await client.get(f"{BASE}/{key}/json/culturalEventInfo/{a}/{b}/")
            resp.raise_for_status()
            rows = parse_cultural_events(resp.json(), on)
        except Exception as exc:
            logger.warning("문화행사 실패: %s", exc)
            break
        out.extend(rows)
        if len(rows) == 0 and p > 0:
            break
    return out
