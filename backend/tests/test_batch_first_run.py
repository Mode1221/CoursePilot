"""첫 구축 시나리오: 카카오만 있고 Google 이 없을 때, 그리고 중간에 죽었을 때."""
from datetime import UTC, datetime

import pytest

from app.batch.districts import DISTRICTS
from app.batch.merge import merge_place, merge_with_stored
from app.batch.places_build import call_plan, collect, run
from app.batch.progress import Progress
from app.config import settings
from app.schemas import Place


class _FakeKakao:
    """카카오 카테고리 검색만 흉내낸다. 호출 기록을 남긴다."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail_on = fail_on or set()

    async def search_category(self, code, lat, lng, radius_m=1000):
        key = f"{lat:.4f}:{code}"
        self.calls.append((key, code))
        if key in self.fail_on:
            raise RuntimeError("rate limit")
        return [
            Place(
                id=f"kakao-{code}-{lat:.3f}-{i}", name=f"장소{i}", category="카페",
                category_code=code, address="서울", lat=lat, lng=lng,
            )
            for i in range(2)
        ]


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


def _enriched(place_id: str) -> Place:
    return Place(
        id=place_id, name="장소0", category="카페", address="서울", lat=37.5445, lng=127.0557,
        rating=4.4, rating_count=250, google_place_id="ChIJtest",
        hours_checked_at=datetime.now(UTC), blog_mentions=999, fact_tags=["주차"],
    )


# ── 멱등성: 재실행이 보강 값을 지우지 않는다 ──────────────────────────────
def test_재수집이_저장된_보강값을_지우지_않는다():
    fresh = Place(id="p1", name="장소0", category="카페", address="서울", lat=37.5, lng=127.0)
    merged = merge_place(fresh, _enriched("p1"))
    assert merged.rating == 4.4
    assert merged.google_place_id == "ChIJtest"
    assert merged.blog_mentions == 999
    assert merged.fact_tags == ["주차"]


def test_새로_들어온_값이_있으면_그것을_쓴다():
    fresh = Place(
        id="p1", name="장소0", category="카페", address="서울", lat=37.5, lng=127.0, rating=3.0
    )
    assert merge_place(fresh, _enriched("p1")).rating == 3.0


def test_가게_정보_자체는_최신_수집분을_따른다():
    fresh = Place(id="p1", name="새 이름", category="술집", address="새 주소",
                  lat=37.6, lng=127.1)
    merged = merge_place(fresh, _enriched("p1"))
    assert (merged.name, merged.address, merged.category) == ("새 이름", "새 주소", "술집")


async def test_구글_키가_나중에_들어와도_이어서_채운다(db):
    """Google 없이 한 번 돌린 뒤, 키가 생겨 다시 돌려도 기존 보강이 살아 있다."""
    from app.places import place_repo

    kakao = _FakeKakao()
    first = await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=kakao, resume=False)
    assert first.upserted > 0
    assert first.hours_filled == 0  # Google 키 없음 → 깔끔하게 스킵

    # 그 사이 일부가 보강됐다고 치고
    stored = place_repo.all(limit=5)
    target = stored[0]
    target.rating, target.google_place_id, target.blog_mentions = 4.2, "ChIJx", 500
    place_repo.upsert_many([target])

    second = await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=kakao, resume=False)
    assert second.merged >= 1
    again = place_repo.get_many([target.id])[target.id]
    assert (again.rating, again.google_place_id, again.blog_mentions) == (4.2, "ChIJx", 500)


async def test_저장분이_없으면_이어받을_것도_없다(db):
    assert merge_with_stored([]) == 0


# ── 중단·재개 ────────────────────────────────────────────────────────────
async def test_중간에_죽으면_남은_조각부터_이어_간다(tmp_path):
    state = Progress(tmp_path / "p.json")
    kakao = _FakeKakao()
    await collect(kakao, DISTRICTS[:2], state)
    first_calls = len(kakao.calls)
    assert first_calls > 0

    # 같은 상태 파일로 다시 시작하면 이미 끝낸 조각은 부르지 않는다
    resumed = Progress(tmp_path / "p.json")
    assert resumed.resumed is True
    kakao2 = _FakeKakao()
    await collect(kakao2, DISTRICTS[:2], resumed)
    assert kakao2.calls == []


async def test_실패한_조각은_끝낸_것으로_치지_않는다(tmp_path):
    lat = f"{DISTRICTS[0].lat:.4f}"
    state = Progress(tmp_path / "p.json")
    kakao = _FakeKakao(fail_on={f"{lat}:CE7"})
    await collect(kakao, DISTRICTS[:1], state)
    assert not state.is_done(DISTRICTS[0].name, "CE7")

    # 재실행 때 그 조각만 다시 시도한다
    resumed = Progress(tmp_path / "p.json")
    kakao2 = _FakeKakao()
    await collect(kakao2, DISTRICTS[:1], resumed)
    assert [c for _, c in kakao2.calls] == ["CE7"]


def test_오래된_진행_상태는_이어받지_않는다(tmp_path):
    from datetime import timedelta

    state = Progress(tmp_path / "p.json")
    state.mark("성수", "FD6")
    later = Progress(tmp_path / "p.json", now=datetime.now(UTC) + timedelta(days=2))
    assert later.resumed is False
    assert later.done == set()


async def test_완주하면_상태를_지운다(db, tmp_path, monkeypatch):
    import app.batch.progress as progress_mod

    monkeypatch.setattr(progress_mod, "DEFAULT_PATH", tmp_path / "p.json")
    await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=_FakeKakao(), resume=True)
    assert not (tmp_path / "p.json").exists()


# ── 콜 수·소요 시간 ──────────────────────────────────────────────────────
def test_전수_수집_콜_수를_미리_계산한다():
    calls, minutes = call_plan(DISTRICTS)
    assert calls == len(DISTRICTS) * 4 * 3  # 상권 × 카테고리 코드 4종 × 3페이지
    assert minutes > 0
