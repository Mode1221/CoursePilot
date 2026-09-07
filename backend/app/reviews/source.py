"""리뷰 수집 어댑터. 네이버 블로그/카페 검색 API(공식) 경유가 원칙 (8장).

크롤링 지양. 키 미설정 시 개발용 Mock 반환.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawReview:
    source: str
    content: str


class ReviewSource(ABC):
    @abstractmethod
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        ...


class MockReviewSource(ReviewSource):
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        samples = [
            f"{place_name} 분위기 조용하고 커피 맛있어요.",
            f"{place_name} 방문했어요. 업체로부터 제공받아 작성한 후기입니다.",  # 협찬
            f"{place_name} 웨이팅 있지만 재방문 의사 있음.",
            f"소정의 원고료를 받아 작성한 {place_name} 체험단 후기.",  # 협찬
        ]
        return [RawReview(source="mock", content=c) for c in samples[:limit]]


def get_review_source() -> ReviewSource:
    # TODO: NaverBlogReviewSource 구현
    return MockReviewSource()
