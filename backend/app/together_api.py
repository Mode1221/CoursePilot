"""합의 코스("먼저 상대에게 묻기") 라우터.

흐름: 생성자가 시작(한 줄 요청 + 링크 토큰 발급) → 상대는 링크로 카드 제출(가입 없음)
→ 생성자도 카드 제출(온보딩 선호로 미리 채움) → 합쳐서 코스 생성(반영 이유 포함)
→ 둘 다 수락하면 확정.

권한: 토큰으로는 **카드 제출·수락**만 된다. AI 명령·삭제·재생성은 생성자만(기존 규칙 유지).
비공개: 합치기 전엔 서로의 답을 보여주지 않고, 합친 뒤에도 예산 숫자는 내보내지 않는다.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.adapters.map_service import get_map_service
from app.pipeline.agent import generate_course
from app.pipeline.consensus import (
    BUDGET_BANDS,
    CONDITIONS,
    CRAVINGS,
    DISLIKES,
    ParticipantInput,
    notes_text,
)
from app.queue import queues
from app.realtime import broadcast_lock, broadcast_message, broadcast_progress, broadcast_state
from app.schemas import Course, TogetherState
from app.session_token import verify
from app.store import store
from app.users import user_store

together_router = APIRouter()

CARD_SPEC = {
    "conditions": list(CONDITIONS),
    "cravings": list(CRAVINGS),
    "dislikes": list(DISLIKES),
    "budget_bands": list(BUDGET_BANDS),
}


class StartRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)  # "토요일 3시 성수"
    owner_name: str = "나"
    partner_name: str = "상대"


class CardRequest(BaseModel):
    name: str | None = None
    condition: str = "normal"
    cravings: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    budget_band: int | None = None
    note: str = Field(default="", max_length=200)


class TogetherStatus(BaseModel):
    """상대에게 보여줄 상태. 답 내용은 없고 누가 냈는지만."""

    course_id: str
    owner_name: str
    partner_name: str
    submitted: list[str]
    built: bool
    accepted_by: list[str]
    request_text: str
    cards: dict
    stale: bool = False


def _owned(course_id: str, user_id: str | None, token: str | None) -> Course:
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    if course.owner_id is not None and course.owner_id != user_id:
        raise HTTPException(status_code=403, detail="코스 생성자만 할 수 있어요")
    if course.owner_id is not None and not verify(course.owner_id, token):
        raise HTTPException(status_code=401, detail="다시 로그인해 주세요")
    return course


def _by_token(token: str) -> Course:
    course = store.find_by_together_token(token)
    if course is None or course.together is None:
        raise HTTPException(status_code=404, detail="링크가 만료됐거나 잘못됐어요")
    return course


def _validate(card: CardRequest) -> None:
    if card.condition not in CONDITIONS:
        raise HTTPException(status_code=400, detail="컨디션 값이 잘못됐어요")
    if any(c not in CRAVINGS for c in card.cravings):
        raise HTTPException(status_code=400, detail="땡기는 것 값이 잘못됐어요")
    if any(d not in DISLIKES for d in card.dislikes):
        raise HTTPException(status_code=400, detail="싫은 것 값이 잘못됐어요")
    if card.budget_band is not None and card.budget_band not in BUDGET_BANDS:
        raise HTTPException(status_code=400, detail="예산 값이 잘못됐어요")


def _status(course: Course) -> TogetherStatus:
    t = course.together
    assert t is not None
    return TogetherStatus(
        course_id=course.id,
        owner_name=t.owner_name,
        partner_name=t.partner_name,
        submitted=sorted(t.inputs),
        built=bool(course.items),
        accepted_by=list(t.accepted_by),
        request_text=t.request_text,
        stale=t.stale,
        cards=CARD_SPEC,
    )


@together_router.post("/courses/{course_id}/together", response_model=TogetherStatus)
async def start_together(
    course_id: str,
    req: StartRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> TogetherStatus:
    """생성자가 "상대에게 물어보기"를 시작한다. 링크 토큰을 만들고 요청 문장을 저장."""
    course = _owned(course_id, x_user_id, x_user_token)
    if course.together is None:
        course.together = TogetherState(
            token=secrets.token_urlsafe(12),
            request_text=req.text,
            owner_name=req.owner_name,
            partner_name=req.partner_name,
        )
    else:
        course.together.request_text = req.text
        course.together.owner_name = req.owner_name
        course.together.partner_name = req.partner_name
    store.save(course)
    return _status(course)


@together_router.get("/courses/{course_id}/together/link")
async def together_link(
    course_id: str,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """상대에게 보낼 토큰. 생성자만 볼 수 있다(공유 뷰에 토큰이 새지 않게 상태 응답과 분리)."""
    course = _owned(course_id, x_user_id, x_user_token)
    if course.together is None:
        raise HTTPException(status_code=404, detail="아직 시작하지 않았어요")
    return {"token": course.together.token}


@together_router.get("/together/{token}", response_model=TogetherStatus)
async def together_status(token: str) -> TogetherStatus:
    """상대가 링크를 열었을 때. 카드 선택지와 진행 상태만 준다(상대의 답은 안 보인다)."""
    return _status(_by_token(token))


@together_router.post("/together/{token}/input", response_model=TogetherStatus)
async def partner_input(token: str, card: CardRequest) -> TogetherStatus:
    """상대의 30초 카드. 가입 없음. 비공개 저장."""
    _validate(card)
    course = _by_token(token)
    t = course.together
    assert t is not None
    name = card.name or t.partner_name
    if name == t.owner_name:
        raise HTTPException(status_code=400, detail="이름이 시작한 사람과 같아요")
    if t.partner_name != name:
        t.inputs.pop(t.partner_name, None)  # 이름을 고쳐 다시 내면 옛 이름의 카드는 버린다
    t.partner_name = name
    t.inputs[name] = ParticipantInput(**card.model_dump(exclude={"name"}), name=name).model_dump()
    _mark_changed(course)
    store.save(course)
    # 시작한 사람 화면이 "상대 답함"으로 바뀌도록 상태를 밀어준다(카드 원문은 _public 이 뺀다)
    await broadcast_state(course.id, _public(course))
    await broadcast_message(course.id, "ai", f"{name}님이 카드를 보냈어요. 합쳐볼게요.")
    return _status(course)


@together_router.post("/courses/{course_id}/together/input", response_model=TogetherStatus)
async def owner_input(
    course_id: str,
    card: CardRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> TogetherStatus:
    """시작한 사람의 카드. 비워 보내면 온보딩 선호로 채운다."""
    _validate(card)
    course = _owned(course_id, x_user_id, x_user_token)
    t = course.together
    if t is None:
        raise HTTPException(status_code=404, detail="아직 시작하지 않았어요")
    name = card.name or t.owner_name
    data = card.model_dump(exclude={"name"})
    if x_user_id and not data["budget_band"]:
        user = user_store.get(x_user_id)
        if user and user.preferences.budget:
            from app.pipeline.agent import BUDGET_CHOICES

            data["budget_band"] = BUDGET_CHOICES.get(user.preferences.budget)
    if t.owner_name != name:
        t.inputs.pop(t.owner_name, None)
    t.owner_name = name
    t.inputs[name] = ParticipantInput(**data, name=name).model_dump()
    _mark_changed(course)
    store.save(course)
    await broadcast_state(course_id, _public(course))
    return _status(course)


@together_router.post("/courses/{course_id}/together/build")
async def build_together(
    course_id: str,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """두 카드를 합쳐 코스를 만든다. 생성자만. 한 명만 냈으면 그 사람 기준 초안(나중에 재조정)."""
    _owned(course_id, x_user_id, x_user_token)

    async def action() -> dict:
        course = store.get(course_id)
        if course is None or course.together is None:
            raise HTTPException(status_code=404, detail="아직 시작하지 않았어요")
        t = course.together
        if not t.inputs:
            raise HTTPException(status_code=400, detail="카드가 아직 없어요")
        inputs = [ParticipantInput(**v) for v in t.inputs.values()]
        prefs = {}
        if x_user_id:
            user = user_store.get(x_user_id)
            if user:
                prefs = user.preferences.model_dump()
        course.locked = True
        await broadcast_lock(course_id, True)

        async def on_progress(stage: str) -> None:
            await broadcast_progress(course_id, stage)

        text = t.request_text
        extra = notes_text(inputs)
        if extra:
            text = f"{text} {extra}"
        try:
            result = await generate_course(
                text,
                get_map_service(),
                prefs,
                on_progress,
                consensus_inputs=inputs,
                consensus_prefer=_prefer(t),
            )
            course.items = result.timeline
            if result.constraints.region:
                course.region = result.constraints.region
            if result.constraints.plan_date:
                course.plan_date = result.constraints.plan_date
            course.party_size = course.party_size or 2
            if result.consensus is not None:
                t.conflict_note = result.consensus.conflict_note
                t.yielded = result.consensus.yielded
                t.attributions = [a.model_dump() for a in result.consensus.attributions]
                t.summary = result.consensus.summary
            t.accepted_by = []  # 새 코스면 수락도 새로
            t.stale = False
        finally:
            course.locked = False
        store.save(course)
        await broadcast_lock(course_id, False)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        who = " · ".join(sorted(t.inputs))
        await broadcast_message(course_id, "ai", f"{who}의 카드를 합쳐 코스를 만들었어요.")
        return {"course": _public(course), "status": _status(course).model_dump()}

    return await queues.run(course_id, action)


@together_router.post("/together/{token}/accept", response_model=TogetherStatus)
async def partner_accept(token: str) -> TogetherStatus:
    course = _by_token(token)
    t = course.together
    assert t is not None
    if not course.items:
        raise HTTPException(status_code=400, detail="아직 코스가 없어요")
    if t.partner_name not in t.accepted_by:
        t.accepted_by.append(t.partner_name)
    store.save(course)
    await broadcast_state(course.id, course.model_dump(mode="json"))
    return _status(course)


@together_router.post("/courses/{course_id}/together/accept", response_model=TogetherStatus)
async def owner_accept(
    course_id: str,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> TogetherStatus:
    course = _owned(course_id, x_user_id, x_user_token)
    t = course.together
    if t is None:
        raise HTTPException(status_code=404, detail="아직 시작하지 않았어요")
    if not course.items:
        raise HTTPException(status_code=400, detail="아직 코스가 없어요")
    if t.owner_name not in t.accepted_by:
        t.accepted_by.append(t.owner_name)
    store.save(course)
    await broadcast_state(course_id, course.model_dump(mode="json"))
    return _status(course)


def _mark_changed(course: Course) -> None:
    """코스를 만든 뒤 카드가 바뀌면 다시 합쳐야 한다 — 수락도 무효."""
    t = course.together
    if t is not None and course.items:
        t.stale = True
        t.accepted_by = []


def _prefer(t: TogetherState) -> str | None:
    """공평 장부: 지난번 양보한 사람이 이번엔 우선. 처음이면 **물어본 상대가 우선** —
    계획한 사람이 먼저 상대를 배려하는 게 이 제품의 약속이다(예전엔 이름순이라 사실상 무작위)."""
    return t.yielded or t.partner_name


def _public(course: Course) -> dict:
    """상대에게도 갈 수 있는 코스 JSON. 카드 원문·토큰은 TogetherState 직렬화가 자동으로 뺀다."""
    return course.model_dump(mode="json")
