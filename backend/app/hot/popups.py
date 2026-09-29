"""팝업·전시를 할거리로 — 기간이 있는 장소를 끝나기 전에만 추천한다.

원천(모두 공식 API):
1. 카카오 로컬 키워드 "{상권} 팝업스토어" — 지도에 임시 등록된 팝업. 끝난 뒤에도 남아 있을 수 있어
   **최근 블로그 언급(21일 이내)** 이 있어야 진행 중으로 본다.
2. 서울시 문화행사 정보 — 전시·체험·공연 시작/종료일이 있다(그날 진행 중인 것만).
3. 서울 실시간 도시데이터의 주변 행사.
결과는 배치가 파일(/data/localdata/popups.json)에 남기고, 런타임은 그 파일을 읽어 후보에 더한다.
"""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import date, timedelta
from pathlib import Path

from app.schemas import Place

logger = logging.getLogger(__name__)

POPUP_WORDS = ("팝업", "popup", "POP-UP", "팝업스토어")
ACTIVE_MENTION_DAYS = 21  # 최근 이 기간 안에 언급이 있어야 진행 중으로 본다
ASSUMED_RUN_DAYS = 14  # 종료일을 모르는 팝업은 마지막 언급 뒤 이만큼만 유효
STORE_PATH = Path(os.environ.get("POPUP_STORE", "/data/localdata/popups.json"))


def looks_like_popup(place: Place) -> bool:
    hay = f"{place.name} {place.category or ''}"
    return any(w.lower() in hay.lower() for w in POPUP_WORDS)


def last_mention(items: list[dict]) -> date | None:
    ds = []
    for it in items:
        raw = str(it.get("postdate") or "")
        if len(raw) == 8:
            try:
                ds.append(date(int(raw[:4]), int(raw[4:6]), int(raw[6:])))
            except ValueError:
                continue
    return max(ds) if ds else None


def active_window(mention: date | None, today: date) -> date | None:
    """최근 언급이 있으면 '마지막 언급 + 14일'까지 진행 중으로 본다. 없으면 None(추천 안 함)."""
    if mention is None or (today - mention).days > ACTIVE_MENTION_DAYS:
        return None
    return mention + timedelta(days=ASSUMED_RUN_DAYS)


def event_to_place(ev: dict, region: str) -> Place | None:
    if not ev.get("name") or ev.get("lat") is None or ev.get("lng") is None:
        return None
    end = ev.get("end")
    return Place(
        id=f"event:{abs(hash((ev['name'], ev.get('place'))))}",
        name=str(ev["name"])[:80],
        category=f"문화,예술 > {ev.get('kind') or '행사'}",
        category_code="CT1",
        address=ev.get("place"),
        lat=float(ev["lat"]),
        lng=float(ev["lng"]),
        price=0 if ev.get("is_free") else None,
        is_popup=True,
        active_until=date.fromisoformat(end) if end else None,
        event_url=ev.get("url"),
        tour_listed=True,
    )


def save(places: list[Place]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps([p.model_dump(mode="json") for p in places], ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_PATH)


_cache: tuple[float, list[Place]] | None = None


def load() -> list[Place]:
    """배치가 남긴 팝업·행사. 파일이 바뀌면 다시 읽는다(mtime)."""
    global _cache
    try:
        mtime = STORE_PATH.stat().st_mtime
    except OSError:
        return []
    if _cache and _cache[0] == mtime:
        return _cache[1]
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        places = [Place.model_validate(d) for d in data]
    except Exception as exc:
        logger.warning("팝업 저장소 읽기 실패: %s", exc)
        return []
    _cache = (mtime, places)
    return places


def active_near(lat: float, lng: float, on: date, radius_km: float = 2.0) -> list[Place]:
    """그날 진행 중이고 반경 안에 있는 팝업·행사."""
    out = []
    for p in load():
        if p.active_until and p.active_until < on:
            continue
        if _km(lat, lng, p.lat, p.lng) <= radius_km:
            out.append(p)
    return out


def _km(a: float, b: float, c: float, d: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
