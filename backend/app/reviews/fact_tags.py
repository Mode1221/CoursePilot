"""팩트 태그 — 블로그 검색 스니펫에서 '사실'만 뽑고 원문은 버린다.

리뷰 원문은 품질 점수에 쓰지 않기로 했고(감정·협찬에 흔들린다), 약관상 가공·
저장도 위험하다. 그래서 스니펫은 메모리에서만 스쳐 지나가고, 남기는 것은
주차·웨이팅·단체석·콘센트·반려동물 같은 사실 축의 태그뿐이다.
"""
from __future__ import annotations

import re

import httpx

from app.config import settings

_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"

# 코스를 짤 때 실제로 판단이 갈리는 '사실' 축만 남긴다(맛·분위기 같은 주관 축 제외).
FACT_TAGS = ("주차", "웨이팅", "단체석", "콘센트", "반려동물", "예약", "좌석")

_TAG_RE = re.compile(r"<[^>]+>")
SNIPPET_LIMIT = 10


def _clean(text: str) -> str:
    """검색 API 는 <b> 강조 태그를 섞어 준다."""
    return _TAG_RE.sub("", text or "")


def tags_from_snippets(snippets: list[str]) -> tuple[list[str], list[str]]:
    """(가능/좋음, 주의) 사실 태그. 주관 축은 걸러낸다."""
    from app.reviews.aspects import extract_aspects

    pros, cons = extract_aspects([_clean(s) for s in snippets])
    return (
        [t for t in pros if t in FACT_TAGS],
        [t for t in cons if t in FACT_TAGS],
    )


async def fetch_snippets(
    client: httpx.AsyncClient, query: str, limit: int = SNIPPET_LIMIT
) -> list[str]:
    """블로그 스니펫을 가져온다. 호출자는 태그만 남기고 원문을 버려야 한다."""
    if not settings.naver_client_id:
        return []
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    try:
        resp = await client.get(
            _BLOG_URL, params={"query": query, "display": limit}, headers=headers
        )
        resp.raise_for_status()
        items = resp.json().get("items") or []
    except Exception:
        return []
    return [f"{i.get('title', '')} {i.get('description', '')}" for i in items]


async def blog_signals(
    client: httpx.AsyncClient, query: str, limit: int = SNIPPET_LIMIT
) -> tuple[int | None, list[str]]:
    """한 번의 검색으로 인지도(건수)와 스니펫을 함께 얻는다(호출 절약).

    스니펫은 태그 추출에만 쓰고 저장하지 않는다.
    """
    if not settings.naver_client_id:
        return None, []
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    try:
        resp = await client.get(
            _BLOG_URL, params={"query": query, "display": limit}, headers=headers
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception:
        return None, []
    items = body.get("items") or []
    total = body.get("total")
    return (
        int(total) if isinstance(total, int) else None,
        [f"{i.get('title', '')} {i.get('description', '')}" for i in items],
    )


async def collect_tags(query: str) -> tuple[list[str], list[str]]:
    """검색 → 태그 추출까지 한 번에. 스니펫은 이 함수 밖으로 나가지 않는다."""
    async with httpx.AsyncClient(timeout=10) as client:
        snippets = await fetch_snippets(client, query)
    if not snippets:
        return [], []
    return tags_from_snippets(snippets)
