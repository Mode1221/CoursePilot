"""CoursePilot 백엔드 진입점.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

import socketio
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.adapters.map_service import get_map_service
from app.config import settings
from app.pipeline.agent import generate_course
from app.pipeline.edit import EditCommand, apply_edit, parse_edit
from app.queue import queues
from app.realtime import broadcast_lock, broadcast_progress, broadcast_state, sio
from app.schemas import Course
from app.bookmarks import bookmark_store
from app.store import store
from app.users import CreditError, Preferences, user_store

api = FastAPI(title="CoursePilot API")


@api.on_event("startup")
async def _startup() -> None:
    from app.db import init_db

    ready = init_db()
    store.enable_db(ready)
    user_store.enable_db(ready)
    bookmark_store.enable_db(ready)


api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    text: str


class SignupRequest(BaseModel):
    phone: str  # 전화번호 인증은 별도 프로세스 가정, 여기선 인증 완료 후 호출
    referrer_id: str | None = None  # 초대한 회원 id (9-4 레퍼럴)

REFERRAL_BONUS = 1


@api.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@api.post("/signup")
async def signup(req: SignupRequest) -> dict:
    user = user_store.create(req.phone)
    if req.referrer_id:  # 신규 가입 시 초대자에게 보너스 크레딧
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
    return [c for c in (store.get(cid) for cid in ids) if c is not None]


@api.put("/users/{user_id}/bookmarks/{course_id}")
async def add_bookmark(user_id: str, course_id: str) -> dict:
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")
    bookmark_store.add(user_id, course_id)
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
    place_id: str
    place_name: str
    query: str = "분위기 방문 후기"


@api.post("/reviews/summary")
async def review_summary(req: ReviewSummaryRequest) -> dict:
    """장소 상세 모달용 리뷰 요약 (4-2 + 8장 RAG)."""
    from app.reviews.rag import ingest_place_reviews, retrieve, summarize_reviews

    db_ready = store._db_ready
    found = await retrieve(req.place_id, req.query, db_ready=db_ready)
    if not found:
        # 최초 조회 시 수집 후 재검색
        await ingest_place_reviews(req.place_id, req.place_name, db_ready)
        found = await retrieve(req.place_id, req.query, db_ready=db_ready)
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
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    if x_user_id is None:
        raise HTTPException(status_code=403, detail="AI 챗봇은 생성자만 사용할 수 있습니다")
    try:
        user = user_store.consume_credit(x_user_id)
    except CreditError:
        raise HTTPException(
            status_code=402, detail="AI에게 질문하려면 포인트를 구매해주세요"
        )
    prefs = user.preferences.model_dump()

    async def action() -> GenerateResponse:
        course.locked = True
        await broadcast_lock(course_id, True)
        async def on_progress(stage: str) -> None:
            await broadcast_progress(course_id, stage)

        relaxed = False
        needs_confirmation = False
        try:
            edit_cmd = parse_edit(req.text) if course.items else EditCommand(action="none")
            if edit_cmd.action != "none":
                # 부분 수정: 해당 카드만 교체/삭제 후 전체 동선 재계산 (4-3)
                await on_progress("editing")
                course.items = await apply_edit(course, edit_cmd, get_map_service())
            else:
                result = await generate_course(req.text, get_map_service(), prefs, on_progress)
                course.items = result.timeline
                relaxed = result.relaxed
                needs_confirmation = result.needs_confirmation
                if result.constraints.region:
                    course.region = result.constraints.region
        finally:
            course.locked = False
        store.save(course)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_lock(course_id, False)
        return GenerateResponse(
            course=course, relaxed=relaxed, needs_confirmation=needs_confirmation
        )

    return await queues.run(course_id, action)


# Socket.IO 를 FastAPI 에 마운트한 ASGI 앱
app = socketio.ASGIApp(sio, other_asgi_app=api)
