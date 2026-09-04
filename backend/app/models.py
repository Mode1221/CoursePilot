"""ORM 모델. 코스는 JSON 상태로 저장, 리뷰는 pgvector 임베딩으로 저장."""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EMBED_DIM = 1536  # text-embedding-3-small 기준


class CourseModel(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="새 코스")
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[dict] = mapped_column(JSON)  # Course 전체 JSON 스냅샷
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class UserModel(Base):
    """전화번호 인증 회원. 크레딧/선호 프로필 보유 (9장)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    phone: Mapped[str] = mapped_column(String, unique=True, index=True)
    credits_limit: Mapped[int] = mapped_column(Integer, default=5)  # 월 무료 N회
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    credit_period: Mapped[str] = mapped_column(String, default="")  # YYYY-MM
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)  # 온보딩 프로필
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewModel(Base):
    """RAG 용 리뷰. 협찬 필터링 후 임베딩 저장 (8장)."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    place_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)  # naver_blog 등
    content: Mapped[str] = mapped_column(Text)
    is_sponsored: Mapped[int] = mapped_column(Integer, default=0)  # 1차 필터 결과
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
