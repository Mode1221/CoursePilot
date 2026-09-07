"""임베딩 유틸. OpenAI 임베딩 사용, 키 없으면 결정론적 해시 기반 폴백(개발용)."""
from __future__ import annotations

import hashlib

from app.models import EMBED_DIM

_EMBED_MODEL = "text-embedding-3-small"


async def embed(text: str) -> list[float]:
    """단건 임베딩. 배치가 필요하면 embed_many 사용."""
    return (await embed_many([text]))[0]


async def embed_many(texts: list[str]) -> list[list[float]]:
    """여러 텍스트를 한 번의 API 호출로 임베딩. 키 없거나 실패 시 해시 폴백."""
    from app.llm_client import get_openai_client

    client = get_openai_client()
    if client is not None:
        try:
            resp = await client.embeddings.create(model=_EMBED_MODEL, input=texts)
            return [d.embedding for d in resp.data]
        except Exception:
            pass
    return [_hash_embed(t) for t in texts]


def _hash_embed(text: str) -> list[float]:
    """개발/오프라인용 결정론적 임베딩. 의미 검색 품질은 없음(형태만 동일)."""
    vec: list[float] = []
    seed = text.encode("utf-8")
    i = 0
    while len(vec) < EMBED_DIM:
        h = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        vec.extend(b / 255.0 for b in h)
        i += 1
    return vec[:EMBED_DIM]
