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
_ready = False  # DB 사용 가능 여부(단일 소스). False면 전 스토어가 인메모리 폴백.


def is_ready() -> bool:
    return _ready


def set_ready(ready: bool) -> None:
    global _ready
    _ready = ready


def _ensure_engine() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _SessionLocal


def SessionLocal() -> Session:
    return _ensure_engine()()


def init_db() -> bool:
    """테이블 및 pgvector 확장 생성. 성공 여부 반환(실패 시 인메모리 폴백).

    pgvector 확장은 없어도 나머지 기능은 다 돌아간다(임베딩 검색만 폴백).
    확장 생성 실패로 테이블까지 못 만들면, 코스·장소가 통째로 인메모리로
    떨어져 재시작마다 사라진다 → 확장 실패는 삼키고 테이블 생성만 본다.
    """
    import logging

    from sqlalchemy import text

    from app import models  # noqa: F401  (모델 등록)

    try:
        _ensure_engine()
        assert _engine is not None
    except Exception:
        return False
    try:
        with _engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        logging.getLogger("coursepilot").warning(
            "pgvector 확장을 만들지 못했습니다 — 임베딩 검색만 폴백하고 나머지는 그대로 씁니다."
        )
    try:
        Base.metadata.create_all(_engine)
        return True
    except Exception:
        return False
