"""전역 장소 스냅샷 저장소(인메모리 폴백)."""
from app.places import MAX_MEM_PLACES, PlaceRepository
from app.schemas import Place


def _place(pid: str) -> Place:
    return Place(id=pid, name=pid, lat=37.5, lng=127.0)


def test_보관_수에_상한이_있다():
    repo = PlaceRepository()
    repo.upsert_many([_place(f"p{i}") for i in range(MAX_MEM_PLACES + 10)])
    assert len(repo._mem) == MAX_MEM_PLACES
    assert "p0" not in repo._mem  # 오래된 것부터 밀려난다
    assert f"p{MAX_MEM_PLACES + 9}" in repo._mem


def test_다시_담으면_최신으로_취급한다():
    repo = PlaceRepository()
    repo.upsert_many([_place("a"), _place("b")])
    repo.upsert_many([_place("a")])
    assert list(repo._mem) == ["b", "a"]


def test_all_은_최근_것을_준다():
    repo = PlaceRepository()
    repo.upsert_many([_place("a"), _place("b"), _place("c")])
    assert [p.id for p in repo.all(limit=2)] == ["b", "c"]
