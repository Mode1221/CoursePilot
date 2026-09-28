"""저장된 장소(배치가 모은 상권 전수)로 코스 후보를 넓힌다.

벤더 키워드 검색은 질의당 10여 곳만 돌려줘서 칸마다 후보가 몇 개뿐이었다
(DB 에 상권당 수백~천여 곳이 있는데도 코스는 늘 같은 몇 곳에서 골랐다).
벤더 결과에 더해, 상권 반경 안의 저장 장소를 칸(식사·카페·할거리·술집)별로 골라 붙인다.
외부 호출은 없다 — 배치가 이미 어댑터로 받아 둔 데이터다.
"""
from __future__ import annotations

import math
import random
import time

from app.schemas import Place

STORED_PER_SLOT = 15  # 칸마다 저장 장소에서 더할 후보 수
MAX_POOL = 120  # 벤더 + 저장 후보 합계 상한(플래너 비용)
DEFAULT_RADIUS_M = 1000
CACHE_TTL_SEC = 600  # 상권 풀은 배치가 하루 한 번 바꾼다 — 요청마다 DB 를 훑지 않는다
_cache: dict[tuple[float, float, int], tuple[float, list[Place]]] = {}
_GENERIC = {"맛집", "카페", "가볼만한곳", "술집", ""}


def region_center_radius(region: str | None, fallback: list[Place]) -> tuple[float, float, int] | None:
    """상권 목록에 있으면 그 중심·반경, 없으면 벤더 결과의 중앙값 좌표."""
    from app.batch.districts import DISTRICTS

    if region:
        for d in DISTRICTS:
            if d.name == region or d.name in region or region in d.name:
                return d.lat, d.lng, max(d.radius_m, 700)
    if fallback:
        lats = sorted(p.lat for p in fallback)
        lngs = sorted(p.lng for p in fallback)
        return lats[len(lats) // 2], lngs[len(lngs) // 2], DEFAULT_RADIUS_M
    return None


def _quality(p: Place) -> float:
    score = 0.0
    if p.rating is not None and (p.rating_count or 0) >= 30:
        score += p.rating
    score += math.log1p(p.blog_mentions or 0) / 3
    if p.tour_listed:
        score += 0.5
    return score


def _matches(p: Place, keyword: str) -> bool:
    if keyword in _GENERIC:
        return True
    text = f"{p.name} {p.category or ''}"
    return any(tok in text for tok in keyword.split())


def stored_candidates(
    region: str | None,
    slot_queries: list[tuple[str, str]],
    vendor: list[Place],
    rng: random.Random | None = None,
) -> list[Place]:
    """칸별로 저장 장소를 골라 돌려준다(벤더 결과와 겹치는 것은 뺀다).

    키워드에 맞는 곳을 먼저, 모자라면 같은 칸의 다른 곳으로 채운다. 매번 같은 곳만 나오지
    않도록 품질 상위 2배수 안에서 무작위로 뽑는다.
    """
    from app.pipeline.planner import classify
    from app.places import place_repo

    area = region_center_radius(region, vendor)
    if area is None or not slot_queries:
        return []
    lat, lng, radius = area
    key = (round(lat, 4), round(lng, 4), radius)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_SEC:
        pool = hit[1]
    else:
        try:
            pool = place_repo.near(lat, lng, radius)
        except Exception:  # 저장소 장애가 코스 생성을 막으면 안 된다
            return []
        _cache[key] = (time.monotonic(), pool)
    if not pool:
        return []
    rng = rng or random.Random()
    have = {p.id for p in vendor}
    by_slot: dict[str, list[Place]] = {}
    for p in pool:
        if p.id in have or p.business_status == "CLOSED_PERMANENTLY":
            continue
        by_slot.setdefault(classify(p), []).append(p)

    out: list[Place] = []
    taken: set[str] = set()
    for slot, kw in slot_queries:
        options = [p for p in by_slot.get(slot, []) if p.id not in taken]
        hits = [p for p in options if _matches(p, kw)]
        rest = [p for p in options if p not in hits] if len(hits) < STORED_PER_SLOT else []
        chosen: list[Place] = []
        for group in (hits, rest):
            need = STORED_PER_SLOT - len(chosen)
            if need <= 0:
                break
            top = sorted(group, key=_quality, reverse=True)[: need * 2]
            chosen += rng.sample(top, min(need, len(top)))
        for p in chosen:
            taken.add(p.id)
        out += chosen
    return out


def clear_cache() -> None:
    _cache.clear()
