"""배치 락: 크론이 겹쳐도 유료 콜이 두 번 나가지 않게 한다."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.batch import lock as lock_mod
from app.batch.lock import STALE_AFTER_MIN, LockBusy, acquire, batch_lock, release
from app.models import Base

NOW = datetime(2026, 9, 9, 4, 0, tzinfo=UTC)


@pytest.fixture()
def db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'lock.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.db.SessionLocal", sessionmaker(engine), raising=False)
    monkeypatch.setattr(lock_mod, "_db_ready", lambda: True)


def test_먼저_잡은_쪽만_실행한다(db):
    assert acquire("places_build", NOW)
    assert not acquire("places_build", NOW)
    release("places_build")
    assert acquire("places_build", NOW)


def test_오래된_락은_무시한다(db):
    acquire("places_build", NOW)
    later = NOW + timedelta(minutes=STALE_AFTER_MIN + 1)
    assert acquire("places_build", later)  # 죽은 프로세스가 남긴 락


def test_컨텍스트_매니저가_해제한다(db):
    with batch_lock("places_refresh"):
        assert not acquire("places_refresh", NOW)
    assert acquire("places_refresh", NOW)


def test_실행_중이면_LockBusy(db):
    acquire("places_refresh")  # 방금 잡은 락(아직 오래되지 않았다)
    with pytest.raises(LockBusy):
        with batch_lock("places_refresh"):
            pass


def test_예외가_나도_락을_푼다(db):
    with pytest.raises(ValueError):
        with batch_lock("places_build"):
            raise ValueError("boom")
    assert acquire("places_build", NOW)


def test_DB가_없으면_막지_않는다(monkeypatch):
    monkeypatch.setattr(lock_mod, "_db_ready", lambda: False)
    assert acquire("places_build") and acquire("places_build")
