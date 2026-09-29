import pytest

from app.metrics import metrics_store
from app.pipeline.llm import decompose
from app.reviews.rag import summarize_reviews


def _externals() -> dict[str, dict]:
    return {e["name"]: e for e in metrics_store.snapshot()["externals"]}


@pytest.mark.asyncio
async def test_decompose_without_key_records_fallback():
    metrics_store.clear()
    await decompose("성수동 저녁 7시")
    assert _externals()["llm.decompose"]["fallback"] == 1


@pytest.mark.asyncio
async def test_review_summary_without_key_records_fallback():
    metrics_store.clear()
    await summarize_reviews(["조용하고 좋았어요"])
    assert _externals()["llm.review_summary"]["fallback_rate"] == 1.0
