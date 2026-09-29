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
CACHE_MAX = 64  # 항목 하나가 장소 최대 3,000개 — 상권 36곳 + 여유
CACHE_TTL_SEC = 600  # 상권 풀은 배치가 하루 한 번 바꾼다 — 요청마다 DB 를 훑지 않는다
_cache: dict[tuple[float, float, int], tuple[float, list[Place]]] = {}
_GENERIC = {"맛집", "카페", "가볼만한곳", "술집", ""}


# 수집 상권(batch/districts.py)에 따로 없지만 자주 말하는 동네 — 중심만 쓴다(반경은 좁게).
# 없으면 벤더 결과 중앙값을 써서 "삼청동"이 1km 넘게 떨어진 인사동·종로3가로 번졌다(운영 점검).
NEIGHBORHOODS: dict[str, tuple[float, float, int]] = {
    "삼청동": (37.5857, 126.9818, 500),
    "서촌": (37.5793, 126.9707, 600),
    "익선동": (37.5742, 126.9895, 400),
    "인사동": (37.5740, 126.9855, 450),
    "경리단길": (37.5390, 126.9900, 500),
    "해방촌": (37.5430, 126.9860, 500),
    "한남동": (37.5345, 127.0010, 700),
    "합정": (37.5495, 126.9139, 600),
    "상수": (37.5478, 126.9227, 500),
    "서울숲": (37.5446, 127.0374, 700),
    "가로수길": (37.5205, 127.0229, 500),
    "압구정": (37.5270, 127.0283, 700),
    "청담": (37.5240, 127.0480, 700),
    "신촌": (37.5598, 126.9425, 700),
    "건대": (37.5404, 127.0692, 700),
    "여의도": (37.5219, 126.9245, 900),
    "문래": (37.5178, 126.8952, 600),
}


def known_center(region: str | None) -> tuple[float, float, int] | None:
    """말한 동네의 중심·반경(상권 목록 또는 NEIGHBORHOODS). 모르면 None."""
    from app.batch.districts import DISTRICTS

    if not region:
        return None
    for name, area in NEIGHBORHOODS.items():  # 좁은 동네가 먼저(“삼청동”이 “북촌”으로 가지 않게)
        if name in region or region.rstrip("동") == name.rstrip("동"):
            return area
    for d in DISTRICTS:
        if d.name == region or d.name in region or region in d.name:
            return d.lat, d.lng, max(d.radius_m, 700)
    return None


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dy = (lat2 - lat1) * 111_000
    dx = (lng2 - lng1) * 111_000 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def keep_near(places: list[Place], region: str | None, min_keep: int = 12) -> list[Place]:
    """말한 동네에서 너무 먼 후보를 뺀다(키워드 검색은 동네 밖 결과도 섞어 준다).

    반경의 1.8배(최소 1km) 밖은 뺀다. 남는 게 너무 적으면(후보가 없는 동네) 그대로 둔다.
    """
    area = known_center(region)
    if area is None:
        return places
    lat, lng, radius = area
    limit = max(1000.0, radius * 1.8)
    near = [p for p in places if distance_m(lat, lng, p.lat, p.lng) <= limit]
    return near if len(near) >= min_keep else places


def region_center_radius(region: str | None, fallback: list[Place]) -> tuple[float, float, int] | None:
    """상권 목록·동네 목록에 있으면 그 중심·반경, 없으면 벤더 결과의 중앙값 좌표."""
    area = known_center(region)
    if area is not None:
        return area
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
        if len(_cache) >= CACHE_MAX:  # 상권 밖 지역도 키가 되므로 끝없이 쌓이지 않게(가장 오래된 것부터)
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
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
