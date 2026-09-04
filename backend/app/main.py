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
from app.queue import queues
from app.realtime import broadcast_lock, broadcast_state, sio
from app.schemas import Course
from app.store import store
from app.users import CreditError, Preferences, user_store

api = FastAPI(title="CoursePilot API")


@api.on_event("startup")
async def _startup() -> None:
    from app.db import init_db

    ready = init_db()
    store.enable_db(ready)
    user_store.enable_db(ready)


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


@api.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@api.post("/signup")
async def signup(req: SignupRequest) -> dict:
    user = user_store.create(req.phone)
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
async def create_course() -> Course:
    return store.create()


@api.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str) -> Course:
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    return course


@api.post("/courses/{course_id}/generate", response_model=Course)
async def generate(
    course_id: str,
    req: GenerateRequest,
    x_user_id: str | None = Header(default=None),
) -> Course:
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

    async def action() -> Course:
        course.locked = True
        await broadcast_lock(course_id, True)
        try:
            result = await generate_course(req.text, get_map_service(), prefs)
            course.items = result.timeline
            if result.constraints.region:
                course.region = result.constraints.region
        finally:
            course.locked = False
        store.save(course)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_lock(course_id, False)
        return course

    return await queues.run(course_id, action)


# Socket.IO 를 FastAPI 에 마운트한 ASGI 앱
app = socketio.ASGIApp(sio, other_asgi_app=api)
