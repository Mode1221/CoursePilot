"""LOCALDATA CSV 내려받기: 부분 실패 허용, 캐시 무효화."""
import io

import httpx
import pytest

from app.adapters.localdata import get_localdata_registry
from app.batch.localdata_fetch import (
    DEFAULT_CSV_URLS,
    MIN_BYTES,
    fetch_all,
    file_name_for,
    headers_for,
    referer_for,
)

CSV = "개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,인허가일자,폐업일자\n3040000,가게,서울 성동구 아차산로 17,서울 성동구 성수동2가 17,영업/정상,영업,20150301,\n"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x.kr/data/seoul_seongdong.csv", "seoul_seongdong.csv"),
        ("https://x.kr/download?id=3", "download_0.csv"),
        ("https://x.kr/a/b/../c.csv", "c.csv"),
        (
            "https://file.localdata.go.kr/file/download/general_restaurants/info",
            "general_restaurants.csv",
        ),
        ("https://file.localdata.go.kr/file/download/rest_cafes/info", "rest_cafes.csv"),
    ],
)
def test_URL에서_안전한_파일명을_만든다(url, expected):
    assert file_name_for(url, 0) == expected


def test_다운로드_URL에서_Referer를_만든다():
    url = "https://file.localdata.go.kr/file/download/rest_cafes/info"
    assert referer_for(url) == "https://file.localdata.go.kr/file/rest_cafes/info"


def test_헤더에_UA와_Referer가_붙는다():
    # 헤더 없이 요청하면 원천이 403 을 준다.
    headers = headers_for(DEFAULT_CSV_URLS[0])
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert headers["Referer"].endswith("/file/general_restaurants/info")


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, bodies):
        self._bodies = bodies
        self.seen: list[httpx.Request] = []

    async def handle_async_request(self, request):
        self.seen.append(request)
        entry = self._bodies.get(str(request.url), (404, "", "text/csv"))
        status, body, ctype = (entry + ("text/csv",))[:3]
        return httpx.Response(status, text=body, headers={"content-type": ctype})


@pytest.fixture()
def transport(monkeypatch):
    box = {}

    def install(bodies):
        original = httpx.AsyncClient
        box["transport"] = transport = _Transport(bodies)

        def factory(*a, **kw):
            kw["transport"] = transport
            return original(*a, **kw)

        monkeypatch.setattr("app.batch.localdata_fetch.httpx.AsyncClient", factory)
        return transport

    install.box = box
    return install


async def test_내려받아_저장한다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    transport({url: (200, CSV)})
    report = await fetch_all([url], str(tmp_path))
    assert report.saved == [url] and report.failed == []
    assert (tmp_path / "a.csv").read_text().startswith("개방자치단체코드")


async def test_한_파일이_실패해도_나머지는_받는다(tmp_path, transport):
    ok, bad = "https://x.kr/a.csv", "https://x.kr/b.csv"
    transport({ok: (200, CSV), bad: (500, "")})
    report = await fetch_all([ok, bad], str(tmp_path))
    assert report.saved == [ok] and report.failed == [bad]


async def test_HTML이_오면_실패로_보고_원인을_남긴다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    transport({url: (200, "<html>점검 중</html>" * 50, "text/html; charset=UTF-8")})
    report = await fetch_all([url], str(tmp_path))
    assert report.failed == [url]
    assert "HTML" in report.errors[url]
    assert not (tmp_path / "a.csv").exists()


async def test_실패해도_임시파일을_남기지_않는다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    transport({url: (500, "")})
    await fetch_all([url], str(tmp_path))
    assert list(tmp_path.iterdir()) == []


async def test_실패해도_기존_파일은_보존된다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    (tmp_path / "a.csv").write_text("예전 내용")
    transport({url: (500, "")})
    await fetch_all([url], str(tmp_path))
    assert (tmp_path / "a.csv").read_text() == "예전 내용"


async def test_요청에_UA와_Referer가_실린다(tmp_path, transport):
    url = "https://file.localdata.go.kr/file/download/rest_cafes/info"
    tr = transport({url: (200, CSV)})
    await fetch_all([url], str(tmp_path))
    request = tr.seen[0]
    assert "Mozilla/5.0" in request.headers["user-agent"]
    assert request.headers["referer"].endswith("/file/rest_cafes/info")


async def test_너무_짧은_응답은_실패로_본다(tmp_path, transport):
    url = "https://x.kr/a.csv"
    transport({url: (200, "x" * (MIN_BYTES - 1))})
    report = await fetch_all([url], str(tmp_path))
    assert report.failed == [url]
    assert not (tmp_path / "a.csv").exists()


async def test_새로_받으면_캐시를_비운다(tmp_path, transport):
    registry = get_localdata_registry()
    registry.load_csv(io.StringIO(CSV))
    assert registry.loaded
    url = "https://x.kr/a.csv"
    transport({url: (200, CSV)})
    await fetch_all([url], str(tmp_path))
    assert not registry.loaded
    get_localdata_registry.cache_clear()


async def test_URL을_안_주면_기본_URL을_쓴다(tmp_path, transport, monkeypatch):
    monkeypatch.setattr("app.batch.localdata_fetch.settings.localdata_csv_urls", [])
    tr = transport({url: (200, CSV) for url in DEFAULT_CSV_URLS})
    report = await fetch_all(None, str(tmp_path))
    assert report.saved == list(DEFAULT_CSV_URLS)
    assert len(tr.seen) == 2


async def test_빈_목록을_명시하면_아무것도_하지_않는다(tmp_path):
    report = await fetch_all([], str(tmp_path))
    assert report.saved == [] and report.failed == []


async def test_저장_경로가_없으면_아무것도_하지_않는다():
    assert (await fetch_all(["https://x.kr/a.csv"], "")).saved == []
