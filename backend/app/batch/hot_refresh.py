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
from app.hot.signals import blog_from_items, combine, is_distinctive, is_landmark, trend_from_series
from app.pipeline.planner import classify, franchise_level
from app.schemas import Place

HOT_SLOTS = ("meal", "cafe", "bar")  # 핫플은 '가게'에만 — 공연장·전시장은 행사가 뜨는 것(팝업·행사 수집이 담당)
SAME_NAME_LIMIT = 3  # 전국에 같은 상호가 이보다 많으면 동네 이름을 붙여 조회

logger = logging.getLogger(__name__)

PER_DISTRICT = 30  # 상권마다 신호를 볼 후보 수
POPUP_RADIUS_KM = 2.5  # 상권 중심에서 이 안의 팝업만
RECHECK_DAYS = 7
REVIEW_BASELINE_DAYS = 28


def _km(a: float, b: float, c: float, d: float) -> float:
    return popup_store._km(a, b, c, d)


def pick_candidates(places: list[Place], now: datetime, force: bool = False) -> dict[str, list[Place]]:
    """가게마다 **가장 가까운 상권 하나**에만 배정 → 확인이 오래된 순·인지도 순으로 상권당 PER_DISTRICT 곳.

    예전엔 상권 반경이 겹치면(성수·서울숲 등) 같은 가게를 두 번 조회해 API 호출이 늘고 시간이 두 배로 걸렸다.
    """
    groups: dict[str, list[Place]] = {d.name: [] for d in DISTRICTS}
    for p in places:
        best: tuple[float, str] | None = None
        for d in DISTRICTS:
            km = _km(d.lat, d.lng, p.lat, p.lng)
            if km <= max(1.2, d.radius_m / 1000 * 1.5) and (best is None or km < best[0]):
                best = (km, d.name)
        if best:
            groups[best[1]].append(p)
    out: dict[str, list[Place]] = {}
    for name, near in groups.items():
        # 같은 이름이 여러 번 등록된 곳(실측: 인왕산둘레길 ×2)은 하나만 — 조회 낭비·중복 표시 방지
        seen_names: set[str] = set()
        uniq = []
        for p in near:
            key = p.name.replace(" ", "")
            if key not in seen_names:
                seen_names.add(key)
                uniq.append(p)
        near = [p for p in uniq if is_hot_target(p)]
        due = [p for p in near if force or not p.hot_checked_at or (now - p.hot_checked_at).days >= RECHECK_DAYS]
        due.sort(key=lambda p: (p.hot_checked_at or datetime.min, -(p.blog_mentions or 0)))
        out[name] = due[:PER_DISTRICT]
    return out


def is_hot_target(p: Place) -> bool:
    """'요즘 뜨는 곳' 딱지를 붙일 대상인가 — 개인 가게(식당·카페·술집)만.

    제외(실측): 고궁·산책로·전망대(계절), 공연장·전시장(그때 하는 행사가 뜨는 것), 프랜차이즈 지점
    (브랜드 광고·신메뉴 검색을 지점이 받아감: "파스쿠찌 잠실역점"), 팝업(기간 한정, 따로 수집).
    """
    if p.is_popup or is_landmark(p.category, p.name, p.category_code):
        return False
    if franchise_level(p) >= 1:
        return False
    return classify(p) in HOT_SLOTS


async def same_name_count(client: httpx.AsyncClient, name: str) -> int | None:
    """전국에 같은 상호가 몇 곳인지(카카오 키워드 검색 total_count). 실패하면 None."""
    from app.config import settings as _s

    if not _s.kakao_rest_api_key:
        return None
    try:
        r = await client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": name, "size": 1},
            headers={"Authorization": f"KakaoAK {_s.kakao_rest_api_key}"},
        )
        r.raise_for_status()
        return int(((r.json().get("meta") or {}).get("total_count")) or 0)
    except Exception:
        return None


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


async def refresh_hotness(
    places: list[Place], today: date | None = None, on_district=None, force: bool = False
) -> list[Place]:
    """on_district(name, done, total, updated_in_district) — 상권마다 진행 표시·중간 저장용.

    예전엔 끝에서 한 번에 저장해, 20분 넘게 돌다 중간에 끄면 전부 날아갔다(실측).
    """
    today = today or date.today()
    now = datetime.now()
    by_district = pick_candidates(places, now, force=force)
    budget = settings.hot_datalab_daily
    updated: list[Place] = []
    total = len(by_district)
    async with httpx.AsyncClient(timeout=10) as client:
        for n, (district, cands) in enumerate(by_district.items(), 1):
            before = len(updated)
            for i in range(0, len(cands), naver_datalab.MAX_GROUPS):
                if budget <= 0:
                    logger.info("데이터랩 예산 소진 — 나머지는 내일")
                    if on_district:
                        on_district(district, n, total, updated[before:])
                    return updated
                chunk = cands[i : i + naver_datalab.MAX_GROUPS]
                # 흔한 이름은 동네를 붙여 조회("익선 옛날순대국밥") — 전국의 '순대국밥' 검색이 섞이지 않게
                # 전국에 같은 상호가 여러 곳이면("로뎀나무아래서") 단어가 고유해 보여도 동네를 붙인다
                keywords: dict[str, str] = {}
                for p in chunk:
                    unique = is_distinctive(p.name)
                    if unique:
                        n_same = await same_name_count(client, p.name)
                        unique = n_same is None or n_same <= SAME_NAME_LIMIT
                    keywords[p.id] = (p.name if unique else f"{district} {p.name}")[:50]
                series = await naver_datalab.weekly_trends(client, list(keywords.values()), today)
                budget -= 1
                for p in chunk:
                    trend = trend_from_series(series.get(keywords[p.id], []))
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
            if on_district:
                on_district(district, n, total, updated[before:])
    return updated


async def refresh_popups(map_service, today: date | None = None, on_district=None) -> list[Place]:
    """상권마다 진행 중인 팝업(카카오 + 최근 언급) + 서울 문화행사·실시간 도시데이터 행사."""
    today = today or date.today()
    found: dict[str, Place] = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for n, d in enumerate(DISTRICTS, 1):
            if on_district:
                on_district(d.name, n, len(DISTRICTS), len(found))
            try:
                cands = await map_service.search_places(d.name, ["팝업스토어"], limit=15)
            except Exception:
                cands = []
            for p in cands:
                if not popup_store.looks_like_popup(p) or p.id in found:
                    continue
                # 카카오 키워드 검색은 먼 곳도 섞어 준다(실측: 남양주 아울렛 팝업) → 상권 반경 안만
                if _km(d.lat, d.lng, p.lat, p.lng) > POPUP_RADIUS_KM:
                    continue
                until = popup_store.active_window(popup_store.last_mention(await _blog_items(client, p.name, 30)), today)
                if until is None or until < today:
                    continue  # 최근 언급이 없거나 추정 종료일이 지났으면 추천하지 않는다
                p.is_popup, p.active_until = True, until
                found[p.id] = p
            st = await seoul_openapi.area_status(client, d.name)
            for ev in (st.events if st else []):
                # 도시데이터 주변 행사엔 분야가 없다 → 제목·장소로 데이트 적합성만 거르고, 기간 문자열에서 종료일을 읽는다
                if not seoul_openapi.is_date_worthy_text(ev.get("name"), ev.get("place")):
                    continue
                ev = {**ev, "end": seoul_openapi.period_end(ev.get("period"))}
                if ev["end"] and date.fromisoformat(ev["end"]) < today:
                    continue
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

