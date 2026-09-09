"""신규 어댑터도 외부 호출 결과를 관측에 남긴다(폴백률로 이상을 잡기 위해)."""
from datetime import date

import httpx
import pytest

from app.adapters.culture import CultureClient
from app.adapters.kakao import KakaoLocalService
from app.adapters.tourapi import TourApiClient
from app.metrics import metrics_store
from app.schemas import Place


def _ext(name: str) -> dict | None:
    return next(
        (e for e in metrics_store.snapshot()["externals"] if e["name"] == name), None
    )


@pytest.fixture(autouse=True)
def clean():
    metrics_store.clear()
    yield
    metrics_store.clear()


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, status=200, text="", json_body=None):
        self._status, self._text, self._json = status, text, json_body

    async def handle_async_request(self, request):
        if self._json is not None:
            return httpx.Response(self._status, json=self._json)
        return httpx.Response(self._status, text=self._text)


async def test_카카오_검색_성공을_기록한다():
    service = KakaoLocalService()
    service._client = httpx.AsyncClient(transport=_Transport(json_body={"documents": []}))
    await service._keyword_page("성수", 1)
    assert _ext("kakao.keyword")["ok"] == 1


async def test_카카오_검색_실패를_기록하고_올린다():
    service = KakaoLocalService()
    service._client = httpx.AsyncClient(transport=_Transport(status=500))
    with pytest.raises(httpx.HTTPStatusError):
        await service._keyword_page("성수", 1)
    assert _ext("kakao.keyword")["fallback"] == 1


async def test_TourAPI_실패를_기록한다():
    class _Broken(TourApiClient):
        def __init__(self):
            self._key = "k"

        async def find(self, name):
            raise RuntimeError("boom")

    await _Broken().enrich(Place(id="p", name="서울숲", lat=37.5, lng=127.0))
    assert _ext("tourapi.enrich")["fallback"] == 1


async def test_KOPIS_실패를_기록한다():
    client = CultureClient()
    client._key = "k"
    client._client = httpx.AsyncClient(transport=_Transport(status=500))
    assert await client.performances(date(2026, 9, 9)) == []
    assert _ext("kopis.performances")["fallback"] == 1


async def test_LOCALDATA_내려받기_결과를_기록한다(tmp_path, monkeypatch):
    from app.batch import localdata_fetch

    original = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = _Transport(text="x" * 500)
        return original(*a, **kw)

    monkeypatch.setattr(localdata_fetch.httpx, "AsyncClient", factory)
    await localdata_fetch.fetch_all(["https://x.kr/a.csv"], str(tmp_path))
    assert _ext("localdata.fetch")["ok"] == 1
