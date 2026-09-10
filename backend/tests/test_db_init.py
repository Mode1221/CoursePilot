"""DB 초기화: pgvector 가 없어도 테이블은 만든다."""
from __future__ import annotations

import app.db as db_mod


def test_pgvector가_없어도_테이블은_만든다(monkeypatch, tmp_path):
    """확장 생성 실패로 테이블까지 못 만들면 전부 인메모리로 떨어져 재시작마다 사라진다."""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    monkeypatch.setattr(db_mod, "_engine", engine, raising=False)
    monkeypatch.setattr(db_mod, "_ensure_engine", lambda: None)
    assert db_mod.init_db() is True  # CREATE EXTENSION 은 sqlite 에서 실패한다


def test_엔진을_못_열면_False(monkeypatch):
    def boom():
        raise RuntimeError("no driver")

    monkeypatch.setattr(db_mod, "_ensure_engine", boom)
    assert db_mod.init_db() is False
