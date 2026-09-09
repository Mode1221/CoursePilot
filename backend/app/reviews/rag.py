"""리뷰 RAG (8장). 수집 → 협찬 1차 필터 → 임베딩 → pgvector 저장 / 검색.

DB 미사용 환경에서는 저장은 생략되고 검색은 빈 결과를 반환한다.
"""
from __future__ import annotations

from app.reviews.embedding import embed, embed_many
from app.reviews.source import get_review_source
from app.reviews.sponsored import sponsored_score

SPONSORED_THRESHOLD = 0.5  # 이 이상이면 협찬 개연성 높음 → 제외


def _keep(content: str) -> bool:
    return sponsored_score(content) < SPONSORED_THRESHOLD


async def ingest_place_reviews(place_id: str, place_name: str, db_ready: bool) -> int:
    """장소 리뷰 수집 후 비협찬 리뷰만 임베딩하여 저장. 저장 건수 반환."""
    reviews = await get_review_source().fetch(place_name)
    kept = [r for r in reviews if _keep(r.content)]  # 다층 협찬 필터
    if not kept:
        return 0
    vectors = await embed_many([r.content for r in kept])  # 배치 임베딩(단일 호출)

    if not db_ready:
        return len(kept)  # 개발용: 저장 대신 필터 통과 건수만

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import ReviewModel

    saved = 0
    with SessionLocal() as s:
        # 재수집 시 같은 리뷰가 쌓이면 검색 결과가 중복으로 채워진다 → 기존 본문은 건너뛴다
        existing = {
            row[0]
            for row in s.execute(
                select(ReviewModel.content).where(ReviewModel.place_id == place_id)
            ).all()
        }
        for r, vector in zip(kept, vectors, strict=False):
            if r.content in existing:
                continue
            existing.add(r.content)
            s.add(
                ReviewModel(
                    place_id=place_id, source=r.source, content=r.content,
                    is_sponsored=0, embedding=vector,
                )
            )
            saved += 1
        s.commit()
    return saved


async def fetch_filtered(place_name: str, limit: int = 5) -> list[str]:
    """수집 → 협찬 다층 필터 적용한 리뷰 텍스트 (DB 불필요, 개발용 폴백)."""
    reviews = await get_review_source().fetch(place_name, limit=limit)
    return [r.content for r in reviews if _keep(r.content)]


def _tag_summary(reviews: list[str]) -> str:
    """LLM 없이 만드는 요약. 리뷰 원문을 그대로 노출하지 않도록 태그로만 정리한다."""
    from app.reviews.aspects import extract_aspects

    pros, cons = extract_aspects(reviews)
    parts: list[str] = []
    if pros:
        parts.append(f"좋은 점: {' · '.join(pros)}")
    if cons:
        parts.append(f"주의할 점: {' · '.join(cons)}")
    if not parts:
        return f"리뷰 {len(reviews)}건을 참고했어요."
    return f"리뷰 {len(reviews)}건 기준 — " + " / ".join(parts)


async def summarize_reviews(reviews: list[str]) -> str:
    """검색된 비협찬 리뷰를 요약. 2차 LLM 필터로 협찬 의심 제외 지시 (8장).

    프로바이더는 조건 분해와 같은 설정(`llm_provider`)을 따른다 — 예전에는
    OpenAI 만 봐서, Anthropic 키만 넣은 배포에서는 항상 태그 요약으로 떨어졌다.
    키가 없거나 호출이 실패하면 원문 대신 애스펙트 태그 요약으로 폴백한다.
    """
    if not reviews:
        return "참고할 리뷰가 없습니다."

    from app.config import settings
    from app.metrics import metrics_store

    try:
        if settings.llm_provider == "openai":
            content = await _summarize_openai(reviews)
        else:
            content = await _summarize_anthropic(reviews)
    except Exception:
        content = None
    metrics_store.record_external("llm.review_summary", ok=bool(content))
    return content or _tag_summary(reviews)


_SUMMARY_SYSTEM = (
    "리뷰를 2~3문장으로 요약. 협찬/체험단 의심 리뷰는 제외하고 참고용으로만 정리."
)


def _joined(reviews: list[str]) -> str:
    return "\n".join(f"- {r}" for r in reviews)


async def _summarize_anthropic(reviews: list[str]) -> str | None:
    from app.config import settings
    from app.llm_client import get_anthropic_client

    client = get_anthropic_client()
    if client is None:
        return None
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        system=_SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": _joined(reviews)}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "\n".join(parts).strip() or None


async def _summarize_openai(reviews: list[str]) -> str | None:
    from app.config import settings
    from app.llm_client import get_openai_client

    client = get_openai_client()
    if client is None:
        return None
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": _joined(reviews)},
        ],
    )
    return resp.choices[0].message.content


def dedupe(contents: list[str]) -> list[str]:
    """순서를 유지하며 같은 본문을 한 번만 남긴다."""
    seen: set[str] = set()
    out: list[str] = []
    for c in contents:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


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
            .where(
                ReviewModel.place_id == place_id,
                ReviewModel.is_sponsored == 0,  # 저장 이후 협찬으로 표시된 건 제외
            )
            .order_by(ReviewModel.embedding.cosine_distance(qvec))
            .limit(k)
        )
        # 같은 본문이 여러 소스로 들어온 경우를 대비해 순서 유지 중복 제거
        return dedupe([row[0] for row in s.execute(stmt).all()])
