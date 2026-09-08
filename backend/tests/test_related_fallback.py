from app.cooccurrence import cooccurrence_store
from app.main import _nearby_popular
from app.places import place_repo
from app.popularity import popularity_store
from app.schemas import Place


def _place(pid: str, lat: float, lng: float, rating: float | None = None) -> Place:
    return Place(id=pid, name=pid, lat=lat, lng=lng, rating=rating)


def setup_function():
    cooccurrence_store._mem.clear()
    popularity_store._mem.clear()
    place_repo._mem.clear()


def test_근처_인기_장소를_돌려준다():
    place_repo.upsert_many(
        [
            _place("base", 37.540, 127.050),
            _place("near_hot", 37.541, 127.051),
            _place("near_cold", 37.542, 127.052),
            _place("far", 37.700, 127.300),
        ]
    )
    popularity_store.bump("near_hot", 5)

    found = _nearby_popular("base", 5)
    ids = [p.id for p in found]
    assert ids[0] == "near_hot"
    assert "far" not in ids
    assert "base" not in ids


def test_인기신호가_없으면_평점순():
    place_repo.upsert_many(
        [_place("base", 37.54, 127.05), _place("a", 37.541, 127.05, 3.0),
         _place("b", 37.541, 127.051, 4.5)]
    )
    assert [p.id for p in _nearby_popular("base", 5)] == ["b", "a"]


def test_기준_장소를_모르면_빈_목록():
    assert _nearby_popular("unknown", 5) == []


def test_근처에_아무것도_없으면_빈_목록():
    place_repo.upsert_many([_place("base", 37.54, 127.05), _place("far", 38.0, 128.0)])
    assert _nearby_popular("base", 5) == []
