"""시드 장소: 키 없이 전체 흐름을 돌리기 위한 데이터와 그 어댑터."""
from collections import Counter

import pytest

from app.adapters.kakao import slot_for
from app.batch.districts import DISTRICTS
from app.batch.seed import MAX_PER_DISTRICT, MIN_PER_DISTRICT, seed_places
from app.config import settings


@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.db as db_mod

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    db_mod.set_ready(True)
    yield db_mod
    db_mod.set_ready(False)


def test_상권마다_충분한_수를_만든다():
    for district in DISTRICTS[:5]:
        places = seed_places((district,))
        assert MIN_PER_DISTRICT <= len(places) <= MAX_PER_DISTRICT


def test_슬롯_분포가_한쪽으로_쏠리지_않는다():
    places = seed_places(DISTRICTS[:6])
    slots = Counter(slot_for(p.category_code, p.category) for p in places)
    assert set(slots) >= {"meal", "cafe", "bar", "activity"}
    total = sum(slots.values())
    assert slots["meal"] / total > 0.3  # 밥집이 가장 많다
    assert all(count / total > 0.05 for count in slots.values())


def test_좌표가_상권_반경_안에_있다():
    from math import asin, cos, radians, sin, sqrt

    for district in DISTRICTS[:4]:
        for place in seed_places((district,)):
            p1, p2 = radians(district.lat), radians(place.lat)
            dp, dl = radians(place.lat - district.lat), radians(place.lng - district.lng)
            x = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
            meters = 2 * 6_371_000 * asin(sqrt(x))
            assert meters <= district.radius_m * 1.1


def test_영업시간과_가격이_슬롯답다():
    places = seed_places(DISTRICTS[:8])
    by_slot = {}
    for place in places:
        by_slot.setdefault(slot_for(place.category_code, place.category), []).append(place)

    # 술집은 밤에 열고 자정을 넘겨 닫는다
    bars = by_slot["bar"]
    assert all(b.open_time.hour >= 17 for b in bars)
    assert all(b.close_time.hour <= 3 for b in bars)
    # 카페가 술집보다 싸다
    cafe_avg = sum(p.price for p in by_slot["cafe"]) / len(by_slot["cafe"])
    bar_avg = sum(p.price for p in by_slot["bar"]) / len(by_slot["bar"])
    assert cafe_avg < bar_avg


def test_다시_만들어도_같은_장소다():
    """재실행이 중복을 만들면 안 된다(id 가 같아야 upsert 로 덮인다)."""
    first = {p.id for p in seed_places(DISTRICTS[:3])}
    second = {p.id for p in seed_places(DISTRICTS[:3])}
    assert first == second


def test_시드는_표시가_붙는다():
    assert all(p.is_mock for p in seed_places(DISTRICTS[:2]))


# ── 어댑터 ────────────────────────────────────────────────────────────────
async def test_시드가_있으면_검색이_그것을_쓴다(db):
    from app.adapters.map_service import get_map_service
    from app.adapters.seeded import has_seed_places
    from app.places import place_repo

    place_repo.upsert_many(seed_places(DISTRICTS[:2]))
    assert has_seed_places() is True

    get_map_service.cache_clear() if hasattr(get_map_service, "cache_clear") else None
    from app.adapters.seeded import SeededPlaceService

    found = await SeededPlaceService().search_places("성수동", [], limit=8)
    assert len(found) == 8
    assert all(p.is_mock for p in found)
    # 한 종류로 쏠리지 않는다 — 코스 칸(밥·카페·술·볼거리)을 채워야 한다
    slots = {slot_for(p.category_code, p.category) for p in found}
    assert len(slots) >= 3


async def test_시드가_없으면_Mock_으로_떨어진다(db):
    from app.adapters.seeded import has_seed_places

    assert has_seed_places() is False


async def test_시드로_코스가_끝까지_만들어진다(db):
    """키 없이도 코스 생성 흐름 전체가 실제 데이터처럼 돈다."""
    from app.adapters.seeded import SeededPlaceService
    from app.pipeline.agent import generate_course
    from app.places import place_repo

    place_repo.upsert_many(seed_places(DISTRICTS[:2]))
    result = await generate_course("성수동 오전 11시 5시간 도보", SeededPlaceService())
    assert len(result.timeline) >= 2
    for item in result.timeline:
        assert item.place.is_mock
        assert item.arrive and item.depart
        assert item.place.price is not None


async def test_시드만_골라_지운다(db):
    """실데이터가 들어와도 진짜 장소는 남아야 한다."""
    from app.places import place_repo
    from app.schemas import Place

    real = Place(id="kakao-1", name="진짜 가게", category="카페", address="서울",
                 lat=37.5445, lng=127.0557)
    place_repo.upsert_many([*seed_places(DISTRICTS[:1]), real])

    stored = place_repo.all(limit=100_000)
    mock_ids = [p.id for p in stored if p.is_mock]
    place_repo.delete_many(mock_ids)

    left = place_repo.all(limit=100_000)
    assert [p.id for p in left] == ["kakao-1"]
