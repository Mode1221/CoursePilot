"""핫플·팝업 배치 — 매일 새벽. 상권마다 후보를 골라 '요즘 뜨는' 신호와 진행 중인 팝업·행사를 갱신한다.

호출 예산: 데이터랩 HOT_DATALAB_DAILY 요청(요청당 5곳), 블로그 검색은 가게당 1회(무료 한도 안).
오래 확인 안 한 곳부터 돈다(순환).
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import httpx

from app.adapters import naver_datalab, seoul_openapi
from app.adapters.naver_search import search_endpoint
from app.batch.districts import DISTRICTS
from app.config import settings
from app.hot import popups as popup_store
from app.hot.signals import blog_from_items, combine, trend_from_series
from app.schemas import Place

logger = logging.getLogger(__name__)

PER_DISTRICT = 30  # 상권마다 신호를 볼 후보 수
RECHECK_DAYS = 7
REVIEW_BASELINE_DAYS = 28


def _km(a: float, b: float, c: float, d: float) -> float:
    return popup_store._km(a, b, c, d)


def pick_candidates(places: list[Place], now: datetime) -> dict[str, list[Place]]:
    """상권 중심 반경 안 장소 중, 확인이 오래된 순 → 인지도 높은 순으로 PER_DISTRICT 곳."""
    out: dict[str, list[Place]] = {}
    for d in DISTRICTS:
        near = [p for p in places if _km(d.lat, d.lng, p.lat, p.lng) <= max(1.2, d.radius_m / 1000 * 1.5)]
        due = [p for p in near if not p.hot_checked_at or (now - p.hot_checked_at).days >= RECHECK_DAYS]
        due.sort(key=lambda p: (p.hot_checked_at or datetime.min, -(p.blog_mentions or 0)))
        out[d.name] = due[:PER_DISTRICT]
    return out


async def _blog_items(client: httpx.AsyncClient, query: str, display: int = 100) -> list[dict]:
    ep = search_endpoint("blog")
    if ep is None:
        return []
    url, headers = ep
    try:
        r = await client.get(url, params={"query": query, "display": display, "sort": "date"}, headers=headers)
        r.raise_for_status()
        return r.json().get("items") or []
    except Exception:
        return []


async def refresh_hotness(places: list[Place], today: date | None = None) -> list[Place]:
    today = today or date.today()
    now = datetime.now()
    by_district = pick_candidates(places, now)
    budget = settings.hot_datalab_daily
    updated: list[Place] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for district, cands in by_district.items():
            for i in range(0, len(cands), naver_datalab.MAX_GROUPS):
                if budget <= 0:
                    logger.info("데이터랩 예산 소진 — 나머지는 내일")
                    return updated
                chunk = cands[i : i + naver_datalab.MAX_GROUPS]
                series = await naver_datalab.weekly_trends(client, [p.name for p in chunk], today)
                budget -= 1
                for p in chunk:
                    trend = trend_from_series(series.get(p.name[:50], []))
                    blog = blog_from_items(await _blog_items(client, f"{district} {p.name}"), today)
                    review_growth = None
                    if p.rating_count and p.review_count_prev:
                        review_growth = p.rating_count / max(1, p.review_count_prev)
                    h = combine(trend, blog, review_growth, p.opened_on, today)
                    p.hot_score, p.hot_reasons, p.sponsored_ratio = h.score, h.reasons, h.sponsored_ratio
                    if p.rating_count and (
                        not p.hot_checked_at or (now - p.hot_checked_at).days >= REVIEW_BASELINE_DAYS
                    ):
                        p.review_count_prev = p.rating_count
                    p.hot_checked_at = now
                    updated.append(p)
    return updated


async def refresh_popups(map_service, today: date | None = None) -> list[Place]:
    """상권마다 진행 중인 팝업(카카오 + 최근 언급) + 서울 문화행사·실시간 도시데이터 행사."""
    today = today or date.today()
    found: dict[str, Place] = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for d in DISTRICTS:
            try:
                cands = await map_service.search_places(d.name, ["팝업스토어"], limit=15)
            except Exception:
                cands = []
            for p in cands:
                if not popup_store.looks_like_popup(p) or p.id in found:
                    continue
                until = popup_store.active_window(popup_store.last_mention(await _blog_items(client, p.name, 30)), today)
                if until is None:
                    continue  # 최근 언급이 없으면 끝났거나 조용한 곳 — 추천하지 않는다
                p.is_popup, p.active_until = True, until
                found[p.id] = p
            st = await seoul_openapi.area_status(client, d.name)
            for ev in (st.events if st else []):
                ep = popup_store.event_to_place(ev, d.name)
                if ep:
                    found.setdefault(ep.id, ep)
        for ev in await seoul_openapi.cultural_events(client, today):
            ep = popup_store.event_to_place(ev, "")
            if ep and any(_km(d.lat, d.lng, ep.lat, ep.lng) <= 2.5 for d in DISTRICTS):
                found.setdefault(ep.id, ep)
    popup_store.save(list(found.values()))
    return list(found.values())


def region_center(region: str | None) -> tuple[float, float] | None:
    if not region:
        return None
    for d in DISTRICTS:
        if d.name == region or d.name in region or region in d.name:
            return d.lat, d.lng
    return None

