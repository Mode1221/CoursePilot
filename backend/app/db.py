"""DB 세션/엔진 구성 (PostgreSQL + pgvector).

DATABASE_URL 이 없거나 드라이버/연결 불가 시 기능은 인메모리 저장소로 폴백한다.
엔진은 지연 생성하여 psycopg 미설치 환경에서도 앱이 import 되도록 한다.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _ensure_engine() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _SessionLocal


def SessionLocal() -> Session:
    return _ensure_engine()()


def init_db() -> bool:
    """테이블 및 pgvector 확장 생성. 성공 여부 반환(실패 시 인메모리 폴백)."""
    from sqlalchemy import text

    from app import models  # noqa: F401  (모델 등록)

    try:
        _ensure_engine()
        assert _engine is not None
        with _engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(_engine)
        return True
    except Exception:
        return False
