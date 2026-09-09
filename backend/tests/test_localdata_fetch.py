"""LOCALDATA CSV 내려받기: 부분 실패 허용, 캐시 무효화."""
import httpx
import pytest

from app.adapters.localdata import get_localdata_registry
from app.batch.localdata_fetch import MIN_BYTES, fetch_all, file_name_for

CSV = "사업장명,도로명전체주소,상세영업상태명,인허가일자,폐업일자\n가게,서울 성동구 아차산로 17,영업/정상,20150301,\n"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x.kr/data/seoul_seongdong.csv", "seoul_seongdong.csv"),
        ("https://x.kr/download?id=3", "download_0.csv"),
        ("https://x.kr/a/b/../c.csv", "c.csv"),
    ],
)
def test_URL에서_안전한_파일명을_만든다(url, expected):
    assert file_name_for(url, 0) == expected


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, bodies: dict[str, tuple[int, str]]):
        self._bodies = bodies

    async def handle_async_request(self, request):
        status, body = self._bodies.get(str(request.url), (404, ""))
        return httpx.Response(status, text=body)


@pytest.fixture()
def transport(monkeypatch):
    def install(bodies):
        original = httpx.AsyncClient

        def factory(*a, **kw):
            kw["transport"] = _Transport(bodies)
            return original(*a, **kw)

        monkeypatch.setattr("app.batch.localdata_fetch.httpx.AsyncClient", factory)

    return install


async def test_내려받아_저장한다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    transport({url: (200, CSV)})
    report = await fetch_all([url], str(tmp_path))
    assert report.saved == [url] and report.failed == []
    assert (tmp_path / "a.csv").read_text().startswith("사업장명")


async def test_한_파일이_실패해도_나머지는_받는다(tmp_path, transport):
    ok, bad = "https://x.kr/a.csv", "https://x.kr/b.csv"
    transport({ok: (200, CSV), bad: (500, "")})
    report = await fetch_all([ok, bad], str(tmp_path))
    assert report.saved == [ok] and report.failed == [bad]


async def test_너무_짧은_응답은_실패로_본다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    transport({url: (200, "x" * (MIN_BYTES - 1))})
    report = await fetch_all([url], str(tmp_path))
    assert report.failed == [url]
    assert not (tmp_path / "a.csv").exists()


async def test_새로_받으면_캐시를_비운다(tmp_path, transport):
    registry = get_localdata_registry()
    registry.load_csv(CSV)
    assert registry.loaded
    url = "https://x.kr/a.csv"
    transport({url: (200, CSV)})
    await fetch_all([url], str(tmp_path))
    assert not registry.loaded
    get_localdata_registry.cache_clear()


async def test_URL이_없으면_아무것도_하지_않는다(tmp_path):
    report = await fetch_all([], str(tmp_path))
    assert report.saved == [] and report.failed == []


async def test_저장_경로가_없으면_아무것도_하지_않는다():
    assert (await fetch_all(["https://x.kr/a.csv"], "")).saved == []
