"""CoursePilot 백엔드 진입점.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.adapters.map_service import get_map_service
from app.bookmarks import bookmark_store
from app.chat import ChatMessage, chat_store
from app.config import settings
from app.constants import DEFAULT_START_TIME
from app.feedback import feedback_store
from app.middleware import RateLimitMiddleware, RequestLogMiddleware
from app.pipeline.agent import generate_course
from app.pipeline.edit import EditCommand, apply_edit, parse_edit
from app.popularity import popularity_store
from app.queue import queues
from app.ratings import rating_store
from app.realtime import (
    broadcast_lock,
    broadcast_message,
    broadcast_progress,
    broadcast_state,
    sio,
)
from app.schemas import Course
from app.store import store
from app.users import CreditError, Preferences, user_store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db import init_db, set_ready

    set_ready(init_db())  # 전 스토어가 참조하는 단일 readiness
    yield


api = FastAPI(title="CoursePilot API", lifespan=lifespan)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# 순서 주의: 나중에 add 한 미들웨어가 바깥쪽 → rate limit 이 로깅보다 먼저 평가되도록
api.add_middleware(RequestLogMiddleware)
api.add_middleware(RateLimitMiddleware)
api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SignupRequest(BaseModel):
    # 전화번호 인증은 별도 프로세스 가정, 여기선 인증 완료 후 호출
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")
    referrer_id: str | None = Field(default=None, max_length=64)  # 9-4 레퍼럴

REFERRAL_BONUS = 1


@api.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@api.post("/signup")
async def signup(req: SignupRequest) -> dict:
    user = user_store.create(req.phone)
    # 신규 가입 시 초대자에게 보너스 크레딧. 자기추천 방지 + 실존 초대자만.
    if (
        req.referrer_id
        and req.referrer_id != user.id
        and user_store.get(req.referrer_id) is not None
    ):
        user_store.grant_credits(req.referrer_id, REFERRAL_BONUS)
    return {"user_id": user.id, "credits_left": user.credits_left}


@api.put("/users/{user_id}/preferences")
async def set_preferences(user_id: str, prefs: Preferences) -> dict:
    user = user_store.set_preferences(user_id, prefs)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"ok": True}


@api.get("/users/{user_id}/credits")
async def get_credits(user_id: str) -> dict:
    user = user_store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    # 사용자에겐 "질문 N회 남음"으로만 노출 (토큰 비노출, 9-5)
    return {"questions_left": user.credits_left}


class PurchaseRequest(BaseModel):
    # 구매할 포인트(질문 횟수). 결제 검증은 별도 프로세스 가정
    points: int = Field(gt=0, le=1000)


@api.post("/users/{user_id}/purchase")
async def purchase_points(user_id: str, req: PurchaseRequest) -> dict:
    """포인트 구매/충전 (9-2). 결제 성공 후 호출. 포인트는 이월된다."""
    if req.points <= 0:
        raise HTTPException(status_code=400, detail="포인트는 1 이상이어야 합니다")
    user = user_store.purchase_points(user_id, req.points)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"questions_left": user.credits_left}


@api.post("/courses", response_model=Course)
async def create_course(x_user_id: str | None = Header(default=None)) -> Course:
    return store.create(owner_id=x_user_id)


@api.get("/users/{user_id}/courses", response_model=list[Course])
async def my_courses(user_id: str) -> list[Course]:
    """마이페이지: 내가 생성한 코스 히스토리 (9-4)."""
    return store.list_by_owner(user_id)


@api.get("/users/{user_id}/bookmarks", response_model=list[Course])
async def my_bookmarks(user_id: str) -> list[Course]:
    ids = bookmark_store.list_course_ids(user_id)
    return store.get_many(ids)


@api.put("/users/{user_id}/bookmarks/{course_id}")
async def add_bookmark(user_id: str, course_id: str) -> dict:
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    bookmark_store.add(user_id, course_id)
    # 북마크된 코스의 장소에 인기 가중(암묵적 정량 신호)
    popularity_store.bump_many([it.place.id for it in course.items], weight=2)
    return {"ok": True}


@api.delete("/users/{user_id}/bookmarks/{course_id}")
async def remove_bookmark(user_id: str, course_id: str) -> dict:
    bookmark_store.remove(user_id, course_id)
    return {"ok": True}


@api.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str) -> Course:
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    return course


class ReviewSummaryRequest(BaseModel):
    place_id: str = Field(min_length=1, max_length=128)
    place_name: str = Field(min_length=1, max_length=200)
    query: str = Field(default="분위기 방문 후기", max_length=200)


@api.post("/reviews/summary")
async def review_summary(req: ReviewSummaryRequest) -> dict:
    """장소 상세 모달용 리뷰 요약 (4-2 + 8장 RAG)."""
    from app.db import is_ready
    from app.reviews.rag import (
        fetch_filtered,
        ingest_place_reviews,
        retrieve,
        summarize_reviews,
    )

    db_ready = is_ready()
    if db_ready:
        found = await retrieve(req.place_id, req.query, db_ready=db_ready)
        if not found:
            # 최초 조회 시 수집 후 재검색
            await ingest_place_reviews(req.place_id, req.place_name, db_ready)
            found = await retrieve(req.place_id, req.query, db_ready=db_ready)
    else:
        # DB 미사용(개발): 수집+협찬 필터만 적용한 리뷰를 바로 요약
        found = await fetch_filtered(req.place_name)
    summary = await summarize_reviews(found)
    return {"summary": summary, "count": len(found)}


class GenerateResponse(BaseModel):
    course: Course
    relaxed: bool  # 조건이 완화되었는지
    needs_confirmation: bool  # 완화로도 부족 → 사용자 확인 필요 (7-4)


@api.post("/courses/{course_id}/generate", response_model=GenerateResponse)
async def generate(
    course_id: str,
    req: GenerateRequest,
    x_user_id: str | None = Header(default=None),
) -> GenerateResponse:
    """챗봇 명령: AI 파이프라인 실행. 액션 큐 직렬화 + Lock broadcast.

    AI 명령은 생성자(로그인 회원)만 가능하며 크레딧 1회 차감(9-3).
    참여자(비로그인)는 수동 편집만 가능 → 403.
    """
    # 존재 확인은 큐 밖에서 빠르게(단, 실제 상태는 lock 안에서 재조회한다)
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")
    if x_user_id is None:
        raise HTTPException(status_code=403, detail="AI 챗봇은 생성자만 사용할 수 있습니다")

    async def action() -> GenerateResponse:
        # 최신 상태를 lock 안에서 재조회 → 동시 요청 간 lost update 방지
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="course not found")

        # 크레딧 소비도 lock 안에서: 원자적 차감 + 실패 시 환불
        try:
            user = user_store.consume_credit(x_user_id)
        except CreditError:
            raise HTTPException(
                status_code=402, detail="AI에게 질문하려면 포인트를 구매해주세요"
            ) from None
        prefs = user.preferences.model_dump()
        # 행동 선호(#13): 이 사용자가 실제 자주 채택한 카테고리를 스코어링에 주입
        from app.behavior import behavior_store

        prefs["behavior_cats"] = behavior_store.top_categories(x_user_id)

        course.locked = True
        await broadcast_lock(course_id, True)
        chat_store.append(course_id, "user", req.text)  # append-only 로그
        await broadcast_message(course_id, "user", req.text)

        async def on_progress(stage: str) -> None:
            await broadcast_progress(course_id, stage)

        relaxed = False
        needs_confirmation = False
        is_edit = False
        old_ids = [it.place.id for it in course.items]
        try:
            edit_cmd = parse_edit(req.text) if course.items else EditCommand(action="none")
            if edit_cmd.action != "none":
                # 부분 수정: 해당 카드만 교체/삭제 후 전체 동선 재계산 (4-3)
                is_edit = True
                await on_progress("editing")
                course.items = await apply_edit(course, edit_cmd, get_map_service())
            else:
                result = await generate_course(req.text, get_map_service(), prefs, on_progress)
                course.items = result.timeline
                relaxed = result.relaxed
                needs_confirmation = result.needs_confirmation
                if result.constraints.region:
                    course.region = result.constraints.region
                # #17: 생성 시 코스 목적함수 점수 저장(만족도 대조용)
                from app.pipeline.planner import course_score

                course.predicted_score = course_score(course.items)
        except Exception:
            user_store.refund_credit(x_user_id)  # 실패 시 소비 크레딧 되돌림
            course.locked = False
            await broadcast_lock(course_id, False)
            raise
        finally:
            course.locked = False
        store.save(course)
        new_ids = [it.place.id for it in course.items]
        # 코스에 채택된 장소에 인기 가점(암묵적 정량 신호)
        popularity_store.bump_many(new_ids)
        # 시간대 컨텍스트(#12): 코스 시작 시간대에 채택 신호 누적
        if not is_edit and course.items:
            from app.timecontext import daypart_of, time_context_store

            first = course.items[0].arrive
            if first:
                time_context_store.bump_many(new_ids, daypart_of(first.hour))
        # 행동 선호(#13): 채택된 장소의 카테고리를 사용자 행동 프로필에 누적
        if course.items:
            from app.pipeline.planner import classify

            behavior_store.bump(x_user_id, [classify(it.place) for it in course.items])
        # 피드백(#16): 완화 제안/적용 로깅
        if needs_confirmation:
            feedback_store.log(course_id, "relax_offered")
        elif relaxed:
            feedback_store.log(course_id, "relax_applied")
        # 생존율(#3): AI 편집으로 교체/삭제돼 밀려난 장소는 -1 로 상쇄(추천 미적중)
        if is_edit:
            dropped = [pid for pid in old_ids if pid not in set(new_ids)]
            popularity_store.bump_many(dropped, weight=-1)

        ai_text = _ai_reply(course, relaxed, needs_confirmation)
        chat_store.append(course_id, "ai", ai_text)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_message(course_id, "ai", ai_text)
        await broadcast_lock(course_id, False)
        return GenerateResponse(
            course=course, relaxed=relaxed, needs_confirmation=needs_confirmation
        )

    return await queues.run(course_id, action)


def _ai_reply(course: Course, relaxed: bool, needs_confirmation: bool) -> str:
    n = len(course.items)
    if needs_confirmation:
        return "조건에 맞는 장소가 부족합니다. 조건을 완화할까요?"
    base = f"{n}곳으로 코스를 구성했어요."
    if relaxed:
        base += " 일부 조건은 완화했어요."
    return base


class RatingRequest(BaseModel):
    stars: int = Field(ge=1, le=5)


@api.post("/places/{place_id}/rating")
async def rate_place(place_id: str, req: RatingRequest) -> dict:
    """장소 원탭 별점(1~5). 자체 정량 신호로 planner 스코어에 반영 (data #9)."""
    rating_store.submit(place_id, req.stars)
    avg = rating_store.averages([place_id]).get(place_id)
    return {"ok": True, "average": avg}


REVISIT_WEIGHT = 2  # 재방문 의사는 장소 단위 강한 긍정(또 가고 싶다)


@api.post("/places/{place_id}/revisit")
async def mark_revisit(place_id: str) -> dict:
    """재방문 의사 토글 (data #10). "또 가고 싶어요" → 장소 인기 강한 가점.

    장소 단위 명시 신호(원탭). 인증 불필요.
    """
    popularity_store.bump(place_id, weight=REVISIT_WEIGHT)
    return {"ok": True}


class FeedbackRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    detail: str = Field(default="", max_length=200)


@api.post("/courses/{course_id}/feedback")
async def post_feedback(course_id: str, req: FeedbackRequest) -> dict:
    """사용자 피드백 기록(#15/#16). 예: 완화 수락/거부."""
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")
    feedback_store.log(course_id, req.kind, req.detail)
    return {"ok": True}


VIEW_WEIGHT = 0.2  # 공유 열람은 약한 완성도 대리 신호(다수 열람 → 완성도 방증)


@api.post("/courses/{course_id}/view")
async def view_course(course_id: str) -> dict:
    """공유 열람 신호 (data #5). 공유 뷰가 열릴 때 코스 장소에 약한 가점.

    완성도 대리지표(열람 많을수록 잘 만든 코스일 가능성). 인증 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    popularity_store.bump_many([it.place.id for it in course.items], weight=VIEW_WEIGHT)
    return {"ok": True}


COMPLETION_WEIGHT = 3  # 완주(실제 방문)는 채택/북마크보다 강한 긍정 신호


@api.post("/courses/{course_id}/complete")
async def complete_course(course_id: str) -> dict:
    """완주 신호("다녀왔어요") (data #6). 실제 방문한 코스의 장소에 강한 인기 가점.

    비로그인 참여자도 누를 수 있어 인증/크레딧 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    place_ids = [it.place.id for it in course.items]
    popularity_store.bump_many(place_ids, weight=COMPLETION_WEIGHT)
    feedback_store.log(course_id, "completed", detail=f"{len(place_ids)}곳")
    return {"ok": True, "places": len(place_ids)}


SATISFACTION_WEIGHT = 2  # 완료 후 만족(👍)/불만족(👎) 원탭 평가 가중


class SatisfactionRequest(BaseModel):
    liked: bool  # 👍=True / 👎=False


@api.post("/courses/{course_id}/satisfaction")
async def rate_satisfaction(course_id: str, req: SatisfactionRequest) -> dict:
    """완료 후 원탭 만족도 👍/👎 (data #8). 텍스트 아님 → 광고·약관 무관.

    만족이면 코스 장소에 +가점, 불만족이면 -가점. 인증 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    weight = SATISFACTION_WEIGHT if req.liked else -SATISFACTION_WEIGHT
    popularity_store.bump_many([it.place.id for it in course.items], weight=weight)
    feedback_store.log(course_id, "liked" if req.liked else "disliked")
    # #17: 예측 점수 vs 실제 만족도 대조 데이터 축적
    if course.predicted_score is not None:
        from app.outcome import outcome_store

        outcome_store.record(course.predicted_score, req.liked)
    return {"ok": True}


class ReorderRequest(BaseModel):
    # 원하는 최종 순서. 빠진 id 는 삭제로 처리.
    place_ids: list[str] = Field(max_length=50)


@api.post("/courses/{course_id}/reorder", response_model=Course)
async def manual_reorder(course_id: str, req: ReorderRequest) -> Course:
    """수동 편집(드래그/삭제). AI 미호출·무료지만 서버 큐로 직렬화 + broadcast (5-1).

    참여자(비로그인)도 가능하므로 인증/크레딧 불필요.
    """
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    async def action() -> Course:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="course not found")
        if course.locked:
            raise HTTPException(status_code=409, detail="AI 처리 중에는 편집할 수 없습니다")

        from app.pipeline.edit import _infer_mode
        from app.pipeline.validation import recompute

        by_id = {it.place.id: it for it in course.items}
        kept_ids = {pid for pid in req.place_ids if pid in by_id}
        # 생존율(#3/#4): 수동 삭제로 빠진 장소는 -1 상쇄(사용자 거부 신호)
        dropped = [pid for pid in by_id if pid not in kept_ids]
        ordered = [by_id[pid] for pid in req.place_ids if pid in by_id]
        if ordered:
            # 앵커는 코스의 원래 시작 시각(전체 최소 도착시각) — 순서가 바뀌어도 유지.
            arrivals = [it.arrive for it in course.items if it.arrive]
            start = min(arrivals) if arrivals else DEFAULT_START_TIME
            course.items = await recompute(
                [it.place for it in ordered], start, _infer_mode(ordered), get_map_service()
            )
        else:
            course.items = []
        store.save(course)
        popularity_store.bump_many(dropped, weight=-1)
        # 재정렬 패턴(#7): 사용자가 확정한 순서의 카테고리 전이를 선호로 학습
        if len(course.items) >= 2:
            from app.pipeline.planner import classify
            from app.sequence import sequence_store

            sequence_store.bump_sequence([classify(it.place) for it in course.items])
        await broadcast_state(course_id, course.model_dump(mode="json"))
        return course

    return await queues.run(course_id, action)


@api.get("/courses/{course_id}/messages", response_model=list[ChatMessage])
async def get_messages(course_id: str) -> list[ChatMessage]:
    """채팅 로그 조회 (append-only). 공유 뷰에서는 노출하지 않음."""
    return chat_store.list(course_id)


# Socket.IO 를 FastAPI 에 마운트한 ASGI 앱
app = socketio.ASGIApp(sio, other_asgi_app=api)
