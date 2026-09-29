"""팩트 태그: 스니펫에서 사실 축만 남기고 원문은 버린다."""
import httpx
import pytest

from app.pipeline.planner import score_place
from app.reviews.fact_tags import FACT_TAGS, blog_signals, collect_tags, tags_from_snippets
from app.schemas import Place, PlanConstraints

SNIPPETS = [
    "<b>성수</b> 카페 주차 가능하고 콘센트 많아요",
    "주차장 넉넉하고 콘센트 많아서 카공하기 좋음",
    "단체 불가라 소규모만 가능해요",
    "단체는 어렵다고 하네요",
    "커피 맛있고 분위기 좋아요",
]


def test_사실_축만_남긴다():
    pros, cons = tags_from_snippets(SNIPPETS)
    assert "주차" in pros and "콘센트" in pros
    assert "단체석" in cons
    # 맛·분위기 같은 주관 축은 태그로 쓰지 않는다
    assert all(tag in FACT_TAGS for tag in [*pros, *cons])


def test_HTML_강조_태그를_지운다():
    pros, _ = tags_from_snippets(["<b>주차</b> 가능", "주차 넉넉"])
    assert "주차" in pros


def test_스니펫이_없으면_빈_태그():
    assert tags_from_snippets([]) == ([], [])


def _place(**kw) -> Place:
    return Place(**{"id": "p", "name": "가게", "lat": 37.5, "lng": 127.0, **kw})


def test_요청_조건과_맞는_사실_태그는_가점():
    c = PlanConstraints(keywords=["단체석"])
    good = _place(fact_tags=["단체석"])
    bad = _place(caution_tags=["단체석"])
    assert score_place(good, c, None) > score_place(_place(), c, None)
    assert score_place(bad, c, None) < score_place(_place(), c, None)


def test_요청과_무관한_태그는_중립():
    c = PlanConstraints(keywords=["조용한"])
    assert score_place(_place(fact_tags=["주차"]), c, None) == score_place(_place(), c, None)


def test_요청_키워드가_없으면_중립():
    c = PlanConstraints()
    assert score_place(_place(fact_tags=["주차"]), c, None) == 0.0


class _Transport(httpx.AsyncBaseTransport):
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status

    async def handle_async_request(self, request):
        return httpx.Response(self._status, json=self._payload)


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr("app.config.settings.naver_client_id", "id")
    monkeypatch.setattr("app.config.settings.naver_client_secret", "secret")


async def test_한_번의_검색으로_건수와_스니펫을_얻는다(key):
    payload = {"total": 4321, "items": [{"title": "주차 가능", "description": "콘센트 많음"}]}
    async with httpx.AsyncClient(transport=_Transport(payload)) as client:
        total, snippets = await blog_signals(client, "가게")
    assert total == 4321 and snippets == ["주차 가능 콘센트 많음"]


async def test_호출_실패는_빈_결과(key):
    async with httpx.AsyncClient(transport=_Transport({}, status=500)) as client:
        assert await blog_signals(client, "가게") == (None, [])


async def test_키가_없으면_호출하지_않는다(monkeypatch):
    monkeypatch.setattr("app.config.settings.naver_client_id", "")
    async with httpx.AsyncClient(transport=_Transport({})) as client:
        assert await blog_signals(client, "가게") == (None, [])
    assert await collect_tags("가게") == ([], [])
