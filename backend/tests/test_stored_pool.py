"""저장 장소로 코스 후보 넓히기 — 벤더 검색(질의당 10여 곳)만으로는 후보가 모자랐다."""
import random

from app.pipeline.stored_pool import STORED_PER_SLOT, stored_candidates
from app.places import PlaceRepository, place_repo
from app.schemas import Place

SEONGSU = (37.5445, 127.0557)


def _p(pid, category, lat=SEONGSU[0], lng=SEONGSU[1], **kw) -> Place:
    return Place(id=pid, name=kw.pop("name", pid), category=category, lat=lat, lng=lng, **kw)


def test_near_는_반경_밖을_뺀다():
    repo = PlaceRepository()
    repo.upsert_many([_p("in", "카페"), _p("out", "카페", lat=SEONGSU[0] + 0.05)])
    assert [p.id for p in repo.near(*SEONGSU, 1000)] == ["in"]


def test_near_는_DB_경로에서도_동작한다(tmp_path, monkeypatch):
    import app.db as db_mod
    from app.config import settings

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    db_mod.set_ready(True)
    try:
        repo = PlaceRepository()
        repo.upsert_many([_p("in", "카페"), _p("out", "카페", lng=SEONGSU[1] + 0.05)])
        assert [p.id for p in repo.near(*SEONGSU, 1000)] == ["in"]
    finally:
        db_mod.set_ready(False)


def test_postgres_질의로_컴파일된다():
    """운영은 Postgres 다 — JSON 좌표 캐스팅이 PG 방언으로 만들어지는지 확인한다."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models import PlaceModel

    q = select(PlaceModel.data).where(PlaceModel.data["lat"].as_float().between(1, 2))
    sql = str(q.compile(dialect=postgresql.dialect()))
    assert "->>" in sql and "FLOAT" in sql.upper()


def test_칸별로_저장_장소를_더하고_키워드에_맞는_곳을_먼저_준다():
    place_repo.upsert_many(
        [_p(f"cafe{i}", "음식점 > 카페") for i in range(30)]
        + [_p("pasta", "음식점 > 양식 > 파스타")]
        + [_p(f"meal{i}", "음식점 > 한식") for i in range(30)]
    )
    got = stored_candidates("성수", [("meal", "파스타"), ("cafe", "카페")], [], random.Random(0))
    meals = [p for p in got if p.id == "pasta" or p.id.startswith("meal")]
    cafes = [p for p in got if p.id.startswith("cafe")]
    assert len(meals) == STORED_PER_SLOT and len(cafes) == STORED_PER_SLOT
    assert "pasta" in {p.id for p in meals}


def test_벤더_결과와_겹치거나_폐업한_곳은_빼고_상권_밖은_안_준다():
    place_repo.upsert_many(
        [
            _p("dup", "카페"),
            _p("closed", "카페", business_status="CLOSED_PERMANENTLY"),
            _p("far", "카페", lat=37.40),
            _p("ok", "카페"),
        ]
    )
    got = stored_candidates("성수", [("cafe", "카페")], [_p("dup", "카페")])
    assert [p.id for p in got] == ["ok"]


def test_모르는_지역이면_벤더_결과_중심을_쓴다():
    place_repo.upsert_many([_p("ok", "카페", lat=35.1, lng=129.0)])
    vendor = [_p("v", "카페", lat=35.1, lng=129.0)]
    assert [p.id for p in stored_candidates("광안리", [("cafe", "")], vendor)] == ["ok"]


async def test_코스_후보에_저장_장소가_들어간다():
    from app.pipeline.agent import _candidates
    from app.schemas import PlanConstraints

    class Vendor:
        async def search_places(self, region, keywords, limit=10):
            return [_p("v1", "카페")]

    place_repo.upsert_many([_p(f"m{i}", "음식점 > 한식") for i in range(20)])
    got = await _candidates(PlanConstraints(region="성수", duration_min=240), Vendor())
    ids = {p.id for p in got}
    assert "v1" in ids and len(ids & {f"m{i}" for i in range(20)}) >= 10


async def test_성격을_말한_교체도_저장_장소에서_찾는다():
    """벤더 검색이 비어도 상권에 저장된 그 성격의 장소로 바꾼다."""
    from app.pipeline.edit import apply_edit, parse_edit
    from app.schemas import Course, TimelineItem

    class Empty:
        async def search_places(self, region, keywords, limit=10):
            return []

        async def get_route(self, origin, dest, mode):
            from app.schemas import Route, TravelMode

            return Route(mode=TravelMode.WALK, duration_min=5, distance_m=300)

    place_repo.upsert_many([_p("gallery", "문화,예술 > 전시관", name="작은 갤러리")])
    course = Course(id="c", region="성수", items=[TimelineItem(place=_p("cafe1", "음식점 > 카페"))])
    items = await apply_edit(course, parse_edit("첫번째를 전시로 바꿔줘"), Empty())
    assert items[0].place.id == "gallery"
