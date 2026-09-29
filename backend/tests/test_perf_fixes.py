"""9/29 성능 점검에서 고친 것들이 되돌아가지 않게."""
from __future__ import annotations

import pytest

from app.config import settings


async def test_벤더_키가_있으면_지도_서비스를_재사용한다(monkeypatch):
    """예전: @lru_cache 가 클래스에 붙어 요청마다 새로 만들었다 → 검색 캐시·연결 재사용이 없었다."""
    from app.adapters.map_service import get_map_service

    monkeypatch.setattr(settings, "kakao_rest_api_key", "k")
    a, b = get_map_service(), get_map_service()
    assert a is b


def test_키가_없으면_재사용하지_않는다():
    from app.adapters.map_service import get_map_service

    assert get_map_service() is not get_map_service()


async def test_이벤트_루프가_바뀌면_새로_만든다(monkeypatch):
    """httpx 클라이언트는 만든 루프에 묶인다 — 배치의 asyncio.run 반복에서 닫힌 루프를 쓰면 안 된다."""
    import app.adapters.map_service as ms

    monkeypatch.setattr(settings, "kakao_rest_api_key", "k")
    first = ms.get_map_service()
    key = ms._SERVICE[0]
    ms._SERVICE = ((123,) + key[1:], first)  # 다른 루프에서 만든 것처럼
    assert ms.get_map_service() is not first


def test_상권_풀_캐시는_크기_상한이_있다(monkeypatch):
    """상권 밖 지역도 캐시 키가 된다 — 끝없이 쌓이지 않게 오래된 것부터 버린다."""
    from app.pipeline import stored_pool
    from app.places import place_repo
    from app.schemas import Place

    stored_pool.clear_cache()
    monkeypatch.setattr(stored_pool, "CACHE_MAX", 3)
    monkeypatch.setattr(place_repo, "near", lambda lat, lng, r: [Place(id=f"s{lat}", name="x", lat=lat, lng=lng)])
    monkeypatch.setattr(
        stored_pool, "region_center_radius", lambda region, fb: (37.0 + len(region) / 100, 127.0, 500)
    )
    for i in range(10):
        stored_pool.stored_candidates("r" * (i + 1), [("meal", "밥")], [])
    assert len(stored_pool._cache) == 3
    stored_pool.clear_cache()


def test_직전_조건_기억은_크기_상한이_있다(monkeypatch):
    from app import chat_api

    chat_api._EFFECTIVE_CONDITION.clear()
    monkeypatch.setattr(chat_api, "EFFECTIVE_CONDITION_MAX", 3)
    for i in range(10):
        chat_api._remember_condition(f"c{i}", "성수")
    assert list(chat_api._EFFECTIVE_CONDITION) == ["c7", "c8", "c9"]
    chat_api._EFFECTIVE_CONDITION.clear()


def test_다시_해줘_재시도는_최대_2번():
    from app import chat_api

    assert chat_api.REGENERATE_RETRIES == 2


@pytest.mark.parametrize(
    ("fragment", "index"),
    [("CAST(data ->> 'lat' AS FLOAT)", "ix_places_lat_lng"), ("state -> 'together' ->> 'token'", "ix_courses_together_token")],
)
def test_표현식_인덱스와_조회식이_같은_모양이다(fragment, index):
    """Postgres 는 인덱스 식과 조회식이 같아야 인덱스를 쓴다(실제 Postgres EXPLAIN 으로 확인한 모양)."""
    from pathlib import Path

    from app.db import EXPRESSION_INDEXES

    ddl = next(d for d in EXPRESSION_INDEXES if index in d)
    assert fragment in ddl
    src = (Path(__file__).resolve().parents[1] / "app").rglob("*.py")
    body = "\n".join(p.read_text() for p in src)
    key = "places.data ->> 'lat'" if "lat" in fragment else "courses.state -> 'together' ->> 'token'"
    assert key in body
