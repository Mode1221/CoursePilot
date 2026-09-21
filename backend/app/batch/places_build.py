"""초기 장소 DB 구축 파이프라인.

    상권 전수 수집(카카오) → 폐업 제거(LOCALDATA) → Google 매핑·영업시간·평점 → upsert

Google Place Details 는 **Enterprise 월 1,000 콜**이 전부다(영업시간·평점이 같은
SKU). 그래서 배치는 하루 20건(월 약 600)만 채우고 나머지 400 은 런타임 몫으로
남긴다. 수집한 전수(약 15,000곳)를 Google 로 채우는 것은 무료로는 불가능하므로,
**상권별 상위 N곳만** 채우는 것을 목표로 한다(docs/DATA_STRATEGY.md).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.adapters.kakao import MAX_PAGE, SLOT_GROUP_CODES, KakaoLocalService
from app.batch.districts import DISTRICTS, District
from app.batch.merge import merge_with_stored
from app.batch.progress import Progress
from app.schemas import Place

logger = logging.getLogger("coursepilot")

# Place Details(Enterprise) 월 1,000 = 배치 600 + 런타임 400.
# 영업시간과 평점을 한 콜로 받으므로 하루 20콜이면 월 600 이다.
DETAILS_PER_DAY = 20
RUNTIME_RESERVE = 400  # 코스 확정 시 갱신에 남겨 두는 몫(배치가 다 쓰면 안 된다)
TOP_PER_DISTRICT = 25  # 상권별로 Google 로 채울 상위 곳 수(24곳 × 25 = 600)
AWARENESS_PER_RUN = 500  # 블로그 검색 일 25,000 한도 안에서 여유 있게

# 예전 이름(호출부 호환). 둘 다 같은 1콜을 쓴다.
HOURS_PER_DAY = DETAILS_PER_DAY
RATINGS_PER_DAY = DETAILS_PER_DAY

# 카테고리 검색에 쓸 그룹 코드(슬롯별 중복 제거)
GROUP_CODES = tuple(dict.fromkeys(c for codes in SLOT_GROUP_CODES.values() for c in codes))


# 카카오 카테고리 검색 1콜에 걸리는 대략의 시간(응답 + 예의상 간격).
SECONDS_PER_CALL = 0.35


def call_plan(districts: tuple[District, ...]) -> tuple[int, float]:
    """수집에 필요한 카카오 콜 수와 예상 소요(분). 로그 첫 줄에 찍는다."""
    calls = len(districts) * len(GROUP_CODES) * MAX_PAGE
    return calls, calls * SECONDS_PER_CALL / 60


@dataclass
class BuildReport:
    collected: int = 0
    closed_removed: int = 0
    hours_filled: int = 0
    awareness_filled: int = 0
    ratings_filled: int = 0
    upserted: int = 0
    merged: int = 0  # 저장된 보강 값을 이어받은 장소 수
    skipped_chunks: int = 0  # 이전 실행에서 이미 끝낸 (상권×카테고리) 조각
    districts: list[str] = field(default_factory=list)


async def collect(
    kakao: KakaoLocalService,
    districts: tuple[District, ...] = DISTRICTS,
    progress: Progress | None = None,
) -> list[Place]:
    """상권×카테고리 전수 수집. 같은 장소는 한 번만.

    progress 를 주면 이미 끝낸 조각은 건너뛴다(중간에 죽어도 이어서 한다).
    """
    found: dict[str, Place] = {}
    for district in districts:
        for code in GROUP_CODES:
            if progress and progress.is_done(district.name, code):
                continue
            try:
                places = await kakao.search_category(
                    code, district.lat, district.lng, district.radius_m
                )
            except Exception as exc:
                # 한 조각 실패가 전체 배치를 멈추지 않는다. 다만 끝낸 것으로
                # 표시하지 않으므로 다음 실행에서 이 조각만 다시 시도한다.
                logger.warning("수집 실패 %s/%s: %s", district.name, code, exc)
                continue
            for place in places:
                found.setdefault(place.id, place)
            if progress:
                progress.mark(district.name, code)
    return list(found.values())


def drop_closed(places: list[Place]) -> tuple[list[Place], int]:
    """LOCALDATA 로 폐업 제거 + 인허가일자(업력) 부착. 대장이 없으면 무동작."""
    from app.adapters.localdata import get_localdata_registry

    registry = get_localdata_registry()
    if not registry.loaded:
        return places, 0
    kept: list[Place] = []
    for place in places:
        record = registry.find(place.name, place.address)
        if record and record.closed:
            continue
        if record and record.opened_on:
            place.opened_on = record.opened_on
        kept.append(place)
    return kept, len(places) - len(kept)


def _details_budget(limit: int) -> int:
    """이번 실행에서 쓸 Google 콜 수. 런타임 몫을 남긴다.

    남은 월 한도가 런타임 예약분보다 적으면 배치는 아예 부르지 않는다 —
    코스 확정 시 영업시간을 못 물어보는 쪽이 더 나쁘다.
    """
    from app.quota import quota_store

    remaining = quota_store.remaining("google.details")
    if remaining is None:
        return limit
    return max(0, min(limit, remaining - RUNTIME_RESERVE))


async def fill_hours(places: list[Place], limit: int = DETAILS_PER_DAY) -> int:
    """만료된 영업시간·평점을 하루 할당량만큼 한 콜씩 채운다(초과분은 다음 실행에서).

    상권별 상위 N곳만 채운다 — 월 1,000 콜로 전수(약 15,000곳)는 불가능하다.
    """
    from app.adapters.google import get_places_client, hours_stale
    from app.popularity import popularity_store

    client = get_places_client()
    budget = _details_budget(limit)
    if not client.enabled or budget <= 0:
        return 0
    scores = popularity_store.scores([p.id for p in places])
    ranked = sorted(places, key=lambda p: scores.get(p.id, 0.0), reverse=True)
    targets = [p for p in ranked[:TOP_PER_DISTRICT] if hours_stale(p)][:budget]
    if not targets:
        return 0
    await asyncio.gather(
        *(client.refresh_details(p) for p in targets), return_exceptions=True
    )
    return sum(1 for p in targets if p.hours_checked_at is not None)


async def fill_ratings(
    places: list[Place], limit: int = DETAILS_PER_DAY, top_per_district: int = TOP_PER_DISTRICT
) -> int:
    """평점은 fill_hours 가 같은 콜로 이미 채운다 — 남은 것만 보충한다.

    영업시간과 평점이 같은 Enterprise SKU 라 따로 부르면 한도만 두 배로 쓴다.
    상위 기준은 아직 자체 신호(인기)뿐이라, 인기 순으로 자른다.
    """
    from app.adapters.google import get_places_client, rating_stale
    from app.popularity import popularity_store

    client = get_places_client()
    budget = _details_budget(limit)
    if not client.enabled or budget <= 0:
        return 0
    scores = popularity_store.scores([p.id for p in places])
    ranked = sorted(places, key=lambda p: scores.get(p.id, 0.0), reverse=True)
    targets = [p for p in ranked[:top_per_district] if rating_stale(p)][:budget]
    if not targets:
        return 0
    await asyncio.gather(
        *(client.refresh_details(p) for p in targets), return_exceptions=True
    )
    return sum(1 for p in targets if p.rating is not None)


async def fill_awareness(places: list[Place], limit: int = AWARENESS_PER_RUN) -> int:
    """블로그 검색으로 인지도(건수)와 사실 태그를 함께 채운다(원문 미저장)."""
    import httpx

    from app.config import settings
    from app.reviews.fact_tags import blog_signals, tags_from_snippets

    if not settings.naver_client_id:
        return 0
    targets = [p for p in places if p.blog_mentions is None][:limit]
    if not targets:
        return 0
    async with httpx.AsyncClient(timeout=10) as client:
        results = await asyncio.gather(
            *(blog_signals(client, p.name) for p in targets), return_exceptions=True
        )
    filled = 0
    for place, result in zip(targets, results, strict=False):
        if not isinstance(result, tuple):
            continue
        total, snippets = result
        if total is None:
            continue
        place.blog_mentions = total
        # 스니펫은 태그만 남기고 버린다(원문 저장 금지).
        place.fact_tags, place.caution_tags = tags_from_snippets(snippets)
        filled += 1
    return filled


async def run(
    districts: tuple[District, ...] = DISTRICTS,
    *,
    hours_limit: int = HOURS_PER_DAY,
    ratings_limit: int = RATINGS_PER_DAY,
    kakao: KakaoLocalService | None = None,
    resume: bool = True,
) -> BuildReport:
    """수집→필터→보강→저장 한 사이클. 매일 돌려 조금씩 채우는 것을 전제로 한다."""
    client = kakao or KakaoLocalService()
    report = BuildReport(districts=[d.name for d in districts])

    calls, minutes = call_plan(districts)
    state = Progress() if resume else None
    if state and state.resumed:
        report.skipped_chunks = len(state.done)
        logger.info(
            "상권 %d곳 수집 재개 — 끝낸 조각 %d개는 건너뛴다(남은 카카오 콜 최대 %d회)",
            len(districts), report.skipped_chunks,
            max(0, calls - report.skipped_chunks * MAX_PAGE),
        )
    else:
        logger.info(
            "상권 %d곳 수집 시작 — 카카오 최대 %d콜(상권 %d × 카테고리 %d × %d페이지), "
            "예상 %.0f분",
            len(districts), calls, len(districts), len(GROUP_CODES), MAX_PAGE, minutes,
        )

    places = await collect(client, districts, state)
    report.collected = len(places)
    # 저장된 보강 값(영업시간·평점·인지도·업력)을 먼저 얹는다.
    # 이걸 빼먹으면 매일 재수집이 어제 채운 것을 지워 영원히 안 채워진다.
    report.merged = merge_with_stored(places)
    places, report.closed_removed = drop_closed(places)
    report.hours_filled = await fill_hours(places, hours_limit)
    report.ratings_filled = await fill_ratings(places, ratings_limit)
    report.awareness_filled = await fill_awareness(places)
    if places:
        from app.places import place_repo

        place_repo.upsert_many(places)
        report.upserted = len(places)
    if state:
        state.clear()  # 완주했으니 다음 실행은 처음부터
    return report
