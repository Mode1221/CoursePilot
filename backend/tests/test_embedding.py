

async def test_빈_입력은_빈_결과():
    from app.reviews.embedding import embed_many

    assert await embed_many([]) == []


async def test_폴백은_메트릭에_남는다():
    from app.metrics import metrics_store
    from app.reviews.embedding import embed_many

    metrics_store.clear()
    await embed_many(["안녕"])
    externals = metrics_store.snapshot()["externals"]
    assert any(e["name"] == "llm.embedding" and e["fallback"] == 1 for e in externals)
