"""세션 큐 직렬화·락 정리."""
from app.queue import SessionQueues


async def test_끝난_세션의_락은_남지_않는다():
    q = SessionQueues()

    async def noop() -> int:
        return 1

    await q.run("c1", noop)
    assert q._locks == {}
    assert q.is_locked("c1") is False


async def test_대기_중에는_락이_유지된다():
    import asyncio

    q = SessionQueues()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow() -> int:
        started.set()
        await release.wait()
        return 1

    async def quick() -> int:
        return 2

    first = asyncio.create_task(q.run("c1", slow))
    await started.wait()
    second = asyncio.create_task(q.run("c1", quick))
    await asyncio.sleep(0)
    assert q.is_locked("c1") is True
    release.set()
    assert await first == 1
    assert await second == 2
    assert q._locks == {}


async def test_큐가_가득_차면_거절한다():
    import asyncio

    import pytest

    from app.queue import MAX_QUEUED_PER_SESSION, QueueOverflow

    q = SessionQueues()
    gate = asyncio.Event()

    async def blocked():
        await gate.wait()

    running = [asyncio.create_task(q.run("c1", blocked)) for _ in range(MAX_QUEUED_PER_SESSION)]
    await asyncio.sleep(0)  # 대기자 등록까지 한 틱

    with pytest.raises(QueueOverflow):
        await q.run("c1", blocked)

    gate.set()
    await asyncio.gather(*running)
    assert q.depth("c1") == 0


async def test_상한을_넘긴_액션은_끊는다(monkeypatch):
    import asyncio

    import pytest

    from app import queue as queue_mod

    monkeypatch.setattr(queue_mod, "ACTION_TIMEOUT_SEC", 0.01)
    q = SessionQueues()

    async def slow():
        await asyncio.sleep(1)

    with pytest.raises(asyncio.TimeoutError):
        await q.run("c1", slow)
    # 끊긴 뒤 큐는 다시 비어 있어야 한다(다음 요청이 들어갈 수 있게)
    assert q.depth("c1") == 0
