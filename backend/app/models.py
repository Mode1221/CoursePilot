"""ORM 모델. 코스는 JSON 상태로 저장, 리뷰는 pgvector 임베딩으로 저장."""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EMBED_DIM = 1536  # text-embedding-3-small 기준


class CourseModel(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="새 코스")
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
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
    points: Mapped[int] = mapped_column(Integer, default=0)  # 구매 포인트(이월, 리셋 없음)
    # 레퍼럴 보너스 지급 횟수(상한 확인용). 번호만 바꿔 무한 초대하는 것을 막는다
    referral_bonus_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)  # 온보딩 프로필
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlaceRatingModel(Base):
    """장소 원탭 별점 집계(합/개수). 자체 명시 정량 신호."""

    __tablename__ = "place_ratings"

    place_id: Mapped[str] = mapped_column(String, primary_key=True)
    sum: Mapped[int] = mapped_column(Integer, default=0)
    count: Mapped[int] = mapped_column(Integer, default=0)


class FeedbackModel(Base):
    """피드백 이벤트(조건 완화 수락/거부 등). 제약 하드니스 학습용."""

    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    detail: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PopularityModel(Base):
    """장소 인기(암묵적 정량 신호). 코스 채택·북마크로 누적."""

    __tablename__ = "place_popularity"

    place_id: Mapped[str] = mapped_column(String, primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[float] = mapped_column(Float, default=0.0)  # unix ts(시간 감쇠용)


class SequenceModel(Base):
    """재정렬 패턴(선호 순서) — 카테고리 인접 전이 누적 (data #7)."""

    __tablename__ = "category_sequences"

    from_cat: Mapped[str] = mapped_column(String, primary_key=True)
    to_cat: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[float] = mapped_column(Float, default=0.0)


class TimeContextModel(Base):
    """시간대 컨텍스트 — 장소×데이파트(아침/낮/저녁) 채택 누적 (data #12)."""

    __tablename__ = "place_time_context"

    place_id: Mapped[str] = mapped_column(String, primary_key=True)
    daypart: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[float] = mapped_column(Float, default=0.0)


class BehaviorModel(Base):
    """행동 선호 — 사용자×카테고리 채택 누적 (data #13)."""

    __tablename__ = "user_behavior"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[float] = mapped_column(Float, default=0.0)


class StrategyModel(Base):
    """Best-of-N 시드 전략 채택 누적 (data #15)."""

    __tablename__ = "seed_strategy"

    label: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class OutcomeModel(Base):
    """코스 예측 점수 vs 실제 만족도 (data #17)."""

    __tablename__ = "course_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    predicted_score: Mapped[float] = mapped_column(Float)
    liked: Mapped[int] = mapped_column(Integer)  # 1=👍 / 0=👎
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CooccurrenceModel(Base):
    """장소 공동 채택(경량 협업 필터링). place_a < place_b 정규화 저장."""

    __tablename__ = "place_cooccurrence"

    place_a: Mapped[str] = mapped_column(String, primary_key=True)
    place_b: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[float] = mapped_column(Float, default=0.0)


class PlaceModel(Base):
    """전역 장소 스냅샷(정규화 Place JSON). CF 추천 등 id→장소 복원용."""

    __tablename__ = "places"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class ChatMessageModel(Base):
    """채팅 로그. append-only (5-2)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)  # user | ai
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BookmarkModel(Base):
    """북마크: 내 코스뿐 아니라 타인이 공유한 코스도 저장 (9-4)."""

    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentModel(Base):
    """처리한 결제 원장. imp_uid 유니크로 같은 결제의 중복 지급을 막는다."""

    __tablename__ = "payments"

    imp_uid: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    points: Mapped[int] = mapped_column(Integer)
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
