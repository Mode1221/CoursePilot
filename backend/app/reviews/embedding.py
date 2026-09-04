"""임베딩 유틸. OpenAI 임베딩 사용, 키 없으면 결정론적 해시 기반 폴백(개발용)."""
from __future__ import annotations

import hashlib

from app.config import settings
from app.models import EMBED_DIM


async def embed(text: str) -> list[float]:
    if settings.openai_api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.embeddings.create(
                model="text-embedding-3-small", input=text
            )
            return resp.data[0].embedding
        except Exception:
            pass
    return _hash_embed(text)


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
