"""리뷰 수집 어댑터.

크롤링 지양. 키 미설정 시 개발용 Mock 반환.

⚠️ 약관 주의 (docs/REVIEW_DATA_SOURCES.md 참고):
- 네이버 검색 API는 2026-09-07 개정으로 결과 데이터의 가공·요약·재배열이 금지되고
  원문 출처+링크를 그대로 노출해야 함 → "AI 요약(8장 RAG)" 용도로는 사용 불가.
  네이버 블로그는 요약 대신 "원문 링크 카드"로만 노출할 것.
- 요약·스코어링용 리뷰 소스는 Google Places(장소당 5개, attribution 필수)를 1순위로 권장.
- 카카오맵은 신뢰도 이슈로 제외.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawReview:
    source: str          # mock | google | naver_blog
    content: str
    rating: float | None = None    # 정량 신호(요약보다 우선)
    author: str | None = None      # 계정 반복 탐지·attribution 용
    url: str | None = None         # 출처 링크(attribution 필수 소스)


class ReviewSource(ABC):
    # 요약/스코어링에 써도 되는 소스인지(약관). 네이버 블로그는 False(원문 링크만).
    summarizable: bool = True

    @abstractmethod
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        ...


class MockReviewSource(ReviewSource):
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        samples = [
            RawReview("mock", f"{place_name} 분위기 조용하고 커피 맛있어요.", rating=4.5),
            RawReview("mock", f"{place_name} 방문했어요. 업체로부터 제공받아 작성한 후기입니다.", rating=5.0),  # 협찬
            RawReview("mock", f"{place_name} 웨이팅 있지만 재방문 의사 있음.", rating=4.0),
            RawReview("mock", f"소정의 원고료를 받아 작성한 {place_name} 체험단 후기.", rating=5.0),  # 협찬
            # 애스펙트 태그가 개발 환경에서도 다양하게 나오도록 축을 넓혀 둔다
            RawReview("mock", f"{place_name} 주차 불가라 대중교통 추천해요.", rating=3.5),
            RawReview("mock", f"{place_name} 콘센트 많아서 오래 앉아 있기 좋아요.", rating=4.5),
            RawReview("mock", f"{place_name} 가성비 좋고 직원분들 친절했습니다.", rating=4.5),
            RawReview("mock", f"{place_name} 예약 필수예요. 자리 좁은 편.", rating=3.5),
        ]
        return samples[:limit]


class GooglePlacesReviewSource(ReviewSource):
    """Google Places 리뷰(장소당 최대 5개). 합법·상업적 허용, attribution 필수.

    키 미설정/실패 시 상위(get_review_source)에서 Mock 으로 폴백한다.
    정책상 리뷰 원문 장기 캐싱을 지양하고 place_id 기준 실시간 조회를 권장.
    """

    summarizable = True
    _TEXTSEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    _DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"

    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        import httpx

        from app.config import settings

        key = settings.google_maps_api_key
        if not key:
            raise RuntimeError("google_maps_api_key 미설정")  # 상위에서 Mock 폴백
        async with httpx.AsyncClient(timeout=10) as client:
            ts = await client.get(
                self._TEXTSEARCH, params={"query": place_name, "key": key, "language": "ko"}
            )
            ts.raise_for_status()
            results = ts.json().get("results") or []
            if not results:
                return []
            place_id = results[0]["place_id"]
            det = await client.get(
                self._DETAILS,
                params={
                    "place_id": place_id,
                    "fields": "review,rating",
                    "key": key,
                    "language": "ko",
                    "reviews_sort": "newest",
                },
            )
            det.raise_for_status()
            reviews = (det.json().get("result") or {}).get("reviews") or []
        # attribution 필수: author_name/url 보존, 원문 장기 캐싱 지양(실시간 조회)
        return [
            RawReview(
                source="google",
                content=r.get("text", ""),
                rating=r.get("rating"),
                author=r.get("author_name"),
                url=r.get("author_url"),
            )
            for r in reviews[:limit]
        ]


class NaverBlogLinkSource(ReviewSource):
    """네이버 블로그 검색 결과 — 2026-09-07 개정으로 요약/가공 금지.

    요약 대상이 아니라 '원문 링크 카드'로만 노출. summarizable=False.
    """

    summarizable = False

    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        # TODO: 검색 API 호출 후 title+link 만 원문 그대로 반환(요약 금지).
        raise NotImplementedError


class SafeReviewSource(ReviewSource):
    """외부 소스 호출이 실패해도 폴백으로 응답을 이어 간다(지도 어댑터와 같은 원칙)."""

    def __init__(self, primary: ReviewSource, fallback: ReviewSource) -> None:
        self._primary = primary
        self._fallback = fallback

    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        from app.metrics import metrics_store

        try:
            reviews = await self._primary.fetch(place_name, limit)
            metrics_store.record_external("reviews.fetch", ok=True)
            return reviews
        except Exception:
            metrics_store.record_external("reviews.fetch", ok=False)
            return await self._fallback.fetch(place_name, limit)


def get_review_source() -> ReviewSource:
    """요약/스코어링용 소스. Google 키가 있으면 Google, 없거나 실패하면 Mock 폴백."""
    from app.config import settings

    if getattr(settings, "google_maps_api_key", ""):
        try:
            return SafeReviewSource(GooglePlacesReviewSource(), MockReviewSource())
        except Exception:
            pass
    return MockReviewSource()
