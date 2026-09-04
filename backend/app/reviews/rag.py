"""리뷰 RAG (8장). 수집 → 협찬 1차 필터 → 임베딩 → pgvector 저장 / 검색.

DB 미사용 환경에서는 저장은 생략되고 검색은 빈 결과를 반환한다.
"""
from __future__ import annotations

from app.reviews.embedding import embed
from app.reviews.source import get_review_source
from app.reviews.sponsored import is_sponsored


async def ingest_place_reviews(place_id: str, place_name: str, db_ready: bool) -> int:
    """장소 리뷰 수집 후 비협찬 리뷰만 임베딩하여 저장. 저장 건수 반환."""
    reviews = await get_review_source().fetch(place_name)
    stored = 0
    rows = []
    for r in reviews:
        sponsored = is_sponsored(r.content)
        if sponsored:
            continue  # 1차 필터에서 명백한 협찬 제외
        vector = await embed(r.content)
        rows.append((r.source, r.content, vector))

    if not db_ready:
        return len(rows)  # 개발용: 저장 대신 필터 통과 건수만

    from app.db import SessionLocal
    from app.models import ReviewModel

    with SessionLocal() as s:
        for source, content, vector in rows:
            s.add(
                ReviewModel(
                    place_id=place_id, source=source, content=content,
                    is_sponsored=0, embedding=vector,
                )
            )
            stored += 1
        s.commit()
    return stored


async def retrieve(place_id: str, query: str, k: int = 3, db_ready: bool = False) -> list[str]:
    """질의와 유사한 비협찬 리뷰 top-k 반환 (pgvector 코사인 거리)."""
    if not db_ready:
        return []

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import ReviewModel

    qvec = await embed(query)
    with SessionLocal() as s:
        stmt = (
            select(ReviewModel.content)
            .where(ReviewModel.place_id == place_id)
            .order_by(ReviewModel.embedding.cosine_distance(qvec))
            .limit(k)
        )
        return [row[0] for row in s.execute(stmt).all()]
