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
