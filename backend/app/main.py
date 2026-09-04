"""CoursePilot 백엔드 진입점.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.adapters.map_service import get_map_service
from app.config import settings
from app.pipeline.agent import generate_course
from app.queue import queues
from app.realtime import broadcast_lock, broadcast_state, sio
from app.schemas import Course
from app.store import store

api = FastAPI(title="CoursePilot API")

api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    text: str


@api.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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
async def generate(course_id: str, req: GenerateRequest) -> Course:
    """챗봇 명령: AI 파이프라인 실행. 액션 큐 직렬화 + Lock broadcast."""
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    async def action() -> Course:
        course.locked = True
        await broadcast_lock(course_id, True)
        try:
            result = await generate_course(req.text, get_map_service())
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
