"""배치 리허설: 키 없이도 수집→필터→저장이 DB 까지 도달하는지 확인한다."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.batch.districts import DISTRICTS
from app.batch.places_build import run
from app.batch.sample_source import SamplePlaceSource
from app.models import Base
from app.pipeline.planner import classify
from app.places import place_repo


@pytest.fixture()
def db(monkeypatch, tmp_path):
    """실제 DB 대신 파일 SQLite 로 같은 경로를 태운다."""
    engine = create_engine(f"sqlite:///{tmp_path/'rehearsal.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.db.SessionLocal", sessionmaker(engine), raising=False)
    monkeypatch.setattr("app.db.is_ready", lambda: True)
    yield


async def test_합성_데이터로_한_상권을_채운다(db):
    report = await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=SamplePlaceSource())
    assert report.collected > 0
    assert report.upserted == report.collected
    stored = place_repo.all(limit=10_000)
    assert len(stored) == report.upserted


async def test_슬롯이_고르게_섞인다(db):
    await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=SamplePlaceSource())
    slots = {classify(p) for p in place_repo.all(limit=10_000)}
    # 밥·카페·술집·활동이 모두 있어야 코스 템플릿이 성립한다
    assert slots == {"meal", "cafe", "bar", "activity"}


async def test_다시_돌려도_중복되지_않는다(db):
    first = await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=SamplePlaceSource())
    await run(DISTRICTS[:1], hours_limit=0, ratings_limit=0, kakao=SamplePlaceSource())
    assert len(place_repo.all(limit=10_000)) == first.upserted


async def test_합성_장소에는_좌표와_카테고리가_있다():
    places = await SamplePlaceSource().search_category("FD6", 37.5445, 127.0557)
    assert places and all(p.lat and p.lng and p.category_code for p in places)


def test_DB_연결에_실패해도_배치가_죽지_않는다(monkeypatch):
    from app.batch.db_setup import connect_db

    monkeypatch.setattr("app.db.init_db", lambda: False)
    monkeypatch.setattr("app.db.is_ready", lambda: False)
    assert connect_db() is False  # 경고만 남기고 계속 진행
