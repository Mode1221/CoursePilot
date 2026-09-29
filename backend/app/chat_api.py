"""채팅 라우터 — AI 코스 생성·완화·수정·질문 답변과 채팅 기록.

main.py 에서 분리했다(1,300줄). 규칙: 엔드포인트는 여기, 해석은 pipeline/*(edit·followup·llm_edit·llm_answer).
"""
from __future__ import annotations

import asyncio
import re

# 개발 기본값 그대로면 비밀번호를 설정하지 않은 것으로 본다
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.adapters.map_service import get_map_service
from app.answers import course_answer, specific_answer
from app.chat import ChatMessage, chat_store
from app.config import settings
from app.constants import DEFAULT_REGION
from app.feedback import feedback_store
from app.pipeline.agent import generate_course
from app.pipeline.decomposition import is_actionable, parse_constraints
from app.pipeline.edit import EditCommand, apply_edit, parse_edit
from app.pipeline.followup import followup_text
from app.popularity import popularity_store
from app.queue import queues
from app.realtime import (
    broadcast_lock,
    broadcast_message,
    broadcast_progress,
    broadcast_state,
)
from app.schemas import Course, PlanConstraints
from app.store import store
from app.users import CreditError, user_store

chat_router = APIRouter()


def _owned_course(course_id: str, user_id: str | None, token: str | None = None) -> Course:
    """생성자 본인만 통과. 코스 id 는 공유 링크로 새어 나가고 사용자 id 도 마찬가지라,
    비밀키가 설정된 환경에서는 서명 토큰까지 맞아야 한다."""
    from app.session_token import verify

    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    # 주인 없는 코스(예전 비로그인 코스)는 아무도 주인이 아니다 — 예전에는 누구나 통과해,
    # 남의 id 를 헤더에 적으면 그 사람 이름으로 AI 를 돌리고 선호·예산을 엿볼 수 있었다.
    if course.owner_id is None or course.owner_id != user_id:
        raise HTTPException(status_code=403, detail="코스 생성자만 변경할 수 있어요")
    if not verify(course.owner_id, token):
        raise HTTPException(status_code=401, detail="다시 로그인해 주세요")
    return course


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class GenerateResponse(BaseModel):
    course: Course
    relaxed: bool  # 조건이 완화되었는지
    needs_confirmation: bool  # 완화로도 부족 → 사용자 확인 필요 (7-4)


def _charge_ai(actor_id: str, request: Request):
    """AI 1회 몫을 쓴다. 실행 주체(생성자)가 체험 계정이면 체험 몫, 회원이면 하루 몫."""
    from app.identity import is_guest
    from app.middleware import client_ip
    from app.usage import charge

    user = user_store.get(actor_id)
    if user is None:
        raise HTTPException(status_code=403, detail="AI 챗봇은 생성자만 사용할 수 있습니다")
    return charge("ai", subject=actor_id, guest=is_guest(user), ip=client_ip(request))


async def _run_charged(course_id: str, action, ticket):
    """큐가 넘쳐 아예 실행되지 않은 요청은 몫을 돌려준다(실행된 뒤의 환불은 action 이 한다)."""
    from app.queue import QueueOverflow

    try:
        return await queues.run(course_id, action)
    except QueueOverflow:
        ticket.release()
        raise


def _ai_actor(course_id: str, user_id: str | None, user_token: str | None, together_token: str | None) -> str | None:
    """AI 명령을 누구 이름으로 실행할지. 생성자이거나, 합의 코스의 상대(링크 토큰)만 허용.

    상대는 가입 없이 링크로 들어온다. 둘이 같이 정하는 제품이라 상대도 챗봇을 쓸 수 있어야 한다 —
    단 검증 기간 무료(FREE_MODE)일 때만(과금 중엔 크레딧 주인이 생성자라 생성자만). 실행 주체는 생성자로 둔다.
    """
    if together_token:
        course = store.get(course_id)
        t = course.together if course else None
        from app.identity import token_matches

        if (
            t is not None
            and course.owner_id is not None
            and settings.free_mode
            and token_matches(t.token, together_token)
        ):
            return course.owner_id
    if user_id is None:
        raise HTTPException(status_code=403, detail="AI 챗봇은 생성자만 사용할 수 있습니다")
    _owned_course(course_id, user_id, user_token)
    return user_id


def _refunder(x_user_id: str | None, ticket):
    """결과를 못 줬거나(실패) 코스를 바꾸지 않은(질문·되묻기) 요청의 크레딧을 돌려준다.

    AI 몫은 경우가 다르다. 실패면 그대로 돌려주지만, 질문·되묻기는 그 사이 LLM(편집 해석·답변)을
    불렀을 수 있다 — 통째로 돌려주면 질문만 반복해 LLM 을 끝없이 쓸 수 있었다. 그래서 AI 몫 대신
    더 넉넉한 '질문' 몫을 쓰고, 그것도 다 썼으면 AI 몫을 쓴 것으로 둔다.
    """
    done = False

    def refund(failed: bool = False) -> None:
        nonlocal done
        if done:
            return
        done = True
        if x_user_id:
            user_store.refund_credit(x_user_id)
        if ticket is None:
            return
        if failed or not x_user_id:
            ticket.release()
            return
        from app.identity import is_guest
        from app.usage import UsageDenied, charge

        user = user_store.get(x_user_id)
        if user is None:
            ticket.release()
            return
        try:
            charge("ask", subject=x_user_id, guest=is_guest(user))
        except UsageDenied:
            return  # 질문 몫도 없다 — AI 몫을 쓴 것으로 둔다
        ticket.release()

    return refund


@chat_router.post("/courses/{course_id}/relax", response_model=GenerateResponse)
async def relax(
    course_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
    x_together_token: str | None = Header(default=None),
) -> GenerateResponse:
    """"조건을 완화해도 좋다"는 답변에 대한 재시도.

    직전 요청 문장을 그대로 다시 쓰되 완화를 강제한다. 사용자가 새 질문을 한 게
    아니므로 크레딧은 차감하지 않는다.
    """
    # 공유받은 사람이 남의 코스를 갈아엎지 못하게 — 생성자 또는 합의 코스 상대(무료 기간)만
    x_user_id = _ai_actor(course_id, x_user_id, x_user_token, x_together_token)
    last_user_text = next(
        (m.text for m in reversed(chat_store.list(course_id)) if m.role == "user"), None
    )
    if last_user_text is None:
        raise HTTPException(status_code=400, detail="완화할 이전 요청이 없습니다")
    ticket = _charge_ai(x_user_id, request) if x_user_id else None

    async def action() -> GenerateResponse:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
        course.locked = True
        await broadcast_lock(course_id, True)
        # 완화 재시도에서도 온보딩 선호(지역·예산·식이)와 행동 선호를 그대로 쓴다 —
        # 예전에는 None 을 넘겨, 완화하면 사용자 프로필이 통째로 무시됐다.
        before_ids = [it.place.id for it in course.items]
        prefs: dict | None = None
        user = user_store.get(x_user_id) if x_user_id else None
        if user is not None:
            from app.behavior import behavior_store

            prefs = user.preferences.model_dump()
            prefs["behavior_cats"] = behavior_store.top_categories(x_user_id)
        try:
            try:
                result = await generate_course(
                    last_user_text, get_map_service(), prefs, None, force_relax=True
                )
            except (Exception, asyncio.CancelledError):
                if ticket is not None:
                    ticket.release()
                raise
            course.items = result.timeline
            if result.constraints.region:
                course.region = result.constraints.region
            if result.constraints.plan_date:
                course.plan_date = result.constraints.plan_date
            if result.constraints.party_size:
                course.party_size = result.constraints.party_size
        finally:
            course.locked = False
            store.save(course)
            await broadcast_lock(course_id, False)
        if [it.place.id for it in course.items] == before_ids:
            # 완화해도 결과가 같으면 같은 문구를 반복하지 않고 다음 수를 제안한다
            ai_text = (
                "완화해도 더 찾지 못했어요. 지역이나 시간대를 바꿔 보시겠어요?"
            )
        else:
            ai_text = _ai_reply(
                course,
                True,
                result.needs_confirmation,
                constraints=result.constraints,
                closed_dropped=result.closed_dropped,
            )
        chat_store.append(course_id, "ai", ai_text)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_message(course_id, "ai", ai_text)
        return GenerateResponse(
            course=course, relaxed=True, needs_confirmation=result.needs_confirmation
        )

    if ticket is None:
        return await queues.run(course_id, action)
    return await _run_charged(course_id, action, ticket)


@chat_router.post("/courses/{course_id}/generate", response_model=GenerateResponse)
async def generate(
    course_id: str,
    req: GenerateRequest,
    request: Request,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
    x_together_token: str | None = Header(default=None),
) -> GenerateResponse:
    """챗봇 명령: AI 파이프라인 실행. 액션 큐 직렬화 + Lock broadcast.

    AI 명령은 생성자(로그인 회원)만 가능하며 크레딧 1회 차감(9-3).
    참여자(비로그인)는 수동 편집만 가능 → 403.
    """
    # 존재 확인은 큐 밖에서 빠르게(단, 실제 상태는 lock 안에서 재조회한다)
    # 생성자, 또는 합의 코스의 상대(링크 토큰·무료 기간)만. 그 외 참여자는 수동 편집만.
    x_user_id = _ai_actor(course_id, x_user_id, x_user_token, x_together_token)
    ticket = _charge_ai(x_user_id, request) if x_user_id else None
    refund = _refunder(x_user_id, ticket)

    async def action() -> GenerateResponse:
        # 최신 상태를 lock 안에서 재조회 → 동시 요청 간 lost update 방지
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")

        # 크레딧 소비도 lock 안에서: 원자적 차감 + 실패 시 환불
        prefs: dict = {}
        if x_user_id:
            try:
                user = user_store.consume_credit(x_user_id)
            except CreditError:
                if ticket is not None:
                    ticket.release()
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
        closed_dropped = 0
        is_edit = False
        region_guessed = False  # 지역을 못 알아들어 기본 지역으로 만든 경우
        pref_region: str | None = None  # 선호 프로필로 지역을 채운 경우
        gen_constraints: PlanConstraints | None = None  # 편집 명령이면 None
        old_items = list(course.items)
        old_ids = [it.place.id for it in course.items]
        old_names = {it.place.id: it.place.name for it in course.items}
        if _UNDO_RE.search(req.text):
            # "되돌려줘" — 직전 AI 변경 전으로. 한 번 더 말하면 다시 앞으로(맞바꿈)
            refund()
            previous_items = _UNDO_SNAPSHOT.get(course_id)
            if previous_items is not None:
                _UNDO_SNAPSHOT[course_id] = old_items
                course.items = previous_items
                ai_text = "직전 상태로 되돌렸어요. 한 번 더 말하면 다시 바꾼 코스로 돌아가요."
            else:
                ai_text = "되돌릴 이전 코스가 없어요."
            course.locked = False
            store.save(course)
            await broadcast_lock(course_id, False)
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        edit_cmd = parse_edit(req.text) if course.items else EditCommand(action="none")
        # "다시 해줘" — 직전 조건을 그대로 다시 쓴다(조건이 없다고 되묻지 않게)
        request_text = req.text
        exclude_ids: set[str] | None = None
        if _REPLACE_ALL_RE.search(req.text):
            # 지금 코스의 장소는 빼고 같은 조건으로 다시 고른다
            previous = _effective_condition(course_id)
            if previous:
                request_text = previous
            exclude_ids = {it.place.id for it in course.items} or None
        elif _REGENERATE_RE.search(req.text):
            previous = _effective_condition(course_id)
            if previous:
                request_text = previous
            # "다시 해줘"에 같은 코스가 나오면 아무 일도 안 한 것처럼 보인다 — 지금 장소는 뺀다
            # (후보가 모자라면 generate_course 가 기존 후보로 되돌아간다)
            exclude_ids = {it.place.id for it in course.items} or None
        elif _CONDITION_CHANGE_RE.search(req.text) or _ALL_QUALITY_RE.search(req.text):
            # 새 값이 앞에 오도록 이어 붙여 파서가 새 값을 우선 잡게 한다
            previous = _effective_condition(course_id)
            if previous:
                request_text = f"{req.text} {previous}"

        # 규칙 파서가 못 알아들은 수정 요청("카페 대신 산책할 데", "너무 비싸")은 LLM 이
        # 지금 코스를 보고 해석한다. 키가 없거나 실패하면 규칙 결과를 그대로 쓴다.
        if (
            course.items
            and request_text == req.text
            and (edit_cmd.action in ("none", "clarify") or _INSTEAD_RE.search(req.text))
        ):
            from app.pipeline.llm_edit import ConditionChange, interpret_edit

            interpreted = await interpret_edit(req.text, course.items)
            if isinstance(interpreted, ConditionChange):
                previous = _effective_condition(course_id) or course.region or ""
                request_text = followup_text(
                    f"{interpreted.text} {req.text}", previous, course.items[0].arrive
                )
                edit_cmd = EditCommand(action="none")
            elif interpreted is not None:
                edit_cmd = interpreted
        # 코스가 있는데 편집 명령이 아니면 새 코스 요청이 아니라 조건 일부를 바꾸는 말이다
        # ("7시에 끝나게", "1시간 늦게", "너무 멀어", "디저트 먹고 싶어") — 직전 조건을 이어받는다.
        if (
            course.items
            and edit_cmd.action == "none"
            and request_text == req.text
            and not _is_question(req.text)
        ):
            previous = _effective_condition(course_id)
            if previous:
                request_text = followup_text(req.text, previous, course.items[0].arrive)

        # 질문("여기 주차 되나요?")에 코스를 갈아엎지 않는다. 편집 명령이 아닌
        # 물음이면 지금 코스로 답하고 크레딧도 돌려준다.
        if edit_cmd.action == "none" and course.items and _is_question(req.text):
            refund()
            course.locked = False
            await broadcast_lock(course_id, False)
            ai_text = specific_answer(course, req.text)
            if ai_text is None:
                from app.pipeline.llm_answer import llm_answer

                ai_text = await llm_answer(course, req.text) or course_answer(course, req.text)
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        if edit_cmd.action == "clarify":
            # 어느 자리를 바꿀지 알 수 없다 → 새 코스를 만들지 않고 되묻는다
            refund()
            course.locked = False
            await broadcast_lock(course_id, False)
            ai_text = "어느 자리를 바꿀까요? 순번(예: 2번째)이나 장소 종류로 말씀해 주세요."
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        # 편집도 아니고 조건·의도도 없는 입력("ㅋㅋㅋ")으로 엉뚱한 코스를 만들고
        # 크레딧까지 태우지 않는다 — 무엇을 원하는지 되묻는다.
        if edit_cmd.action == "none" and not is_actionable(
            request_text, parse_constraints(request_text)
        ):
            refund()
            course.locked = False
            await broadcast_lock(course_id, False)
            ai_text = '어떤 모임인지 알려주세요. 예: "성수동에서 토요일 저녁 데이트"'
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        try:
            if edit_cmd.action != "none":
                # 부분 수정: 해당 카드만 교체/삭제 후 전체 동선 재계산 (4-3)
                is_edit = True
                await on_progress("editing")
                course.items = await apply_edit(course, edit_cmd, get_map_service())
            else:
                result = await generate_course(
                    request_text,
                    get_map_service(),
                    prefs,
                    on_progress,
                    exclude_place_ids=exclude_ids,
                )
                if exclude_ids and len(result.timeline) < len(old_ids):
                    # "다시 해줘" — 지금 장소를 다 빼니 곳 수가 줄었다(후보가 적은 지역).
                    # 한 곳씩만 다시 쓰도록 허용해 가며, 곳 수를 지키면서 가장 많이 바뀐 코스를 쓴다.
                    # 최대 2번만 — 곳 수만큼 순서대로 다시 만들면(각각 LLM 분해 포함) 60초 큐 제한에 걸려 504 가 났다.
                    for keep in old_ids[:REGENERATE_RETRIES]:
                        retry = await generate_course(
                            request_text,
                            get_map_service(),
                            prefs,
                            on_progress,
                            exclude_place_ids=set(old_ids) - {keep},
                        )
                        if len(retry.timeline) >= len(old_ids):
                            result = retry
                            break
                course.items = result.timeline
                relaxed = result.relaxed
                needs_confirmation = result.needs_confirmation
                closed_dropped = result.closed_dropped
                gen_constraints = result.constraints
                if course.items:
                    _remember_condition(course_id, request_text)  # 다음 후속 요청의 바탕
                region_guessed = result.constraints.region is None
                # 문장에 지역이 없어 저장된 선호로 채웠다면 그 사실을 알린다
                if (
                    result.constraints.region
                    and parse_constraints(request_text).region is None
                    and prefs.get("region") == result.constraints.region
                ):
                    pref_region = result.constraints.region
                if result.constraints.region:
                    course.region = result.constraints.region
                if result.constraints.plan_date:  # 캘린더 내보내기 기준일
                    course.plan_date = result.constraints.plan_date
                if result.constraints.party_size:
                    course.party_size = result.constraints.party_size
                # #17: 생성 시 코스 목적함수 점수 저장(만족도 대조용)
                from app.pipeline.planner import course_score

                course.predicted_score = course_score(course.items)
        except (Exception, asyncio.CancelledError):
            # 큐 타임아웃은 CancelledError 로 들어온다(BaseException 이라 Exception 에 안 걸린다).
            # 그때도 크레딧은 돌려줘야 한다 — 결과를 못 받았으니까.
            refund(failed=True)  # 실패 시 소비 크레딧·AI 몫 되돌림
            course.locked = False
            await broadcast_lock(course_id, False)
            raise
        finally:
            course.locked = False
        store.save(course)
        new_ids = [it.place.id for it in course.items]
        if old_items and new_ids != old_ids:
            _remember_undo(course_id, old_items)
        # 코스에 채택된 장소에 인기 가점(암묵적 정량 신호)
        popularity_store.bump_many(new_ids)
        # 시간대 컨텍스트(#12): 코스 시작 시간대에 채택 신호 누적
        if not is_edit and course.items:
            from app.timecontext import daypart_of, time_context_store

            first = course.items[0].arrive
            if first:
                time_context_store.bump_many(new_ids, daypart_of(first.hour))
        # 행동 선호(#13): 채택된 장소의 카테고리를 사용자 행동 프로필에 누적
        if course.items and x_user_id:
            from app.pipeline.planner import classify

            behavior_store.bump(x_user_id, [classify(it.place) for it in course.items])
        # 협업 필터링(활용): 함께 채택된 장소 쌍 공동 채택 누적
        if len(new_ids) >= 2:
            from app.cooccurrence import cooccurrence_store

            cooccurrence_store.bump_course(new_ids)
        # 전역 장소 저장소: 등장 장소 스냅샷 보관(CF 추천 id→장소 복원용)
        if course.items:
            from app.places import place_repo

            place_repo.upsert_many([it.place for it in course.items])
        # 피드백(#16): 완화 제안/적용 로깅
        if needs_confirmation:
            feedback_store.log(course_id, "relax_offered")
        elif relaxed:
            feedback_store.log(course_id, "relax_applied")
        # 생존율(#3): AI 편집으로 교체/삭제돼 밀려난 장소는 -1 로 상쇄(추천 미적중)
        if is_edit:
            dropped = [pid for pid in old_ids if pid not in set(new_ids)]
            popularity_store.bump_many(dropped, weight=-1)

        if is_edit and edit_cmd.action == "clear":
            ai_text = "코스를 비웠어요. 어떤 모임인지 다시 말씀해 주세요."
        elif is_edit and new_ids == old_ids and edit_cmd.action == "reorder":
            # 이미 최적 동선이면 "못 찾았다"가 아니라 그대로 좋다고 알린다
            refund()
            ai_text = "이미 이동거리가 가장 짧은 순서예요. 그대로 두는 걸 추천해요."
        elif is_edit and new_ids == old_ids:
            # 없는 순번·카테고리를 지목하면 아무것도 바뀌지 않는다 → 알리고 크레딧도 돌려준다
            refund()
            ai_text = "요청하신 자리를 찾지 못했어요. 순번(예: 2번째)이나 장소 종류로 다시 말씀해 주세요."
        elif is_edit and edit_cmd.action == "keep":
            ai_text = f"말씀하신 곳만 남겼어요. 이제 {len(course.items)}곳이에요."
        elif is_edit and edit_cmd.action in ("replace", "remove", "add"):
            ai_text = _edit_reply(course, edit_cmd.action, old_ids, new_ids, old_names)
        elif is_edit and edit_cmd.action in ("reorder", "swap"):
            # 순서만 바꾼 경우엔 "N곳으로 구성했어요" 대신 무엇이 달라졌는지 말한다
            total = sum(
                it.travel_to_next.duration_min for it in course.items if it.travel_to_next
            )
            order = " → ".join(it.place.name for it in course.items)
            ai_text = f"순서를 바꿨어요. {order} (총 이동 {total}분)"
        else:
            ai_text = _ai_reply(
                course,
                relaxed,
                needs_confirmation,
                region_guessed,
                gen_constraints,
                pref_region,
                closed_dropped,
            )
            if old_ids and course.items and not needs_confirmation:
                ai_text = f"{ai_text} {_change_note(old_ids, new_ids)}"
        chat_store.append(course_id, "ai", ai_text)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_message(course_id, "ai", ai_text)
        await broadcast_lock(course_id, False)
        return GenerateResponse(
            course=course, relaxed=relaxed, needs_confirmation=needs_confirmation
        )

    if ticket is None:
        return await queues.run(course_id, action)
    return await _run_charged(course_id, action, ticket)


# "다시 해줘", "새로 만들어줘" — 직전 조건 그대로 다시 만들라는 뜻
_REGENERATE_RE = re.compile(
    r"(?:다시|새로|새롭게|리롤|다른\s*걸?로)\s*(?:한번|한\s*번)?\s*"
    r"(?:해|만들|찾|추천|짜|구성)|처음부터\s*다시"
)


# 코스별로 실제 생성에 쓴 조건 문장(후속 요청이 덧붙은 결과). 채팅 기록만 보면 "디저트 먹고 싶어"
# 같은 후속 문장이 조건 문장으로 잡혀 지역·시간이 사라진다. 재시작하면 채팅 기록으로 폴백한다.
_EFFECTIVE_CONDITION: dict[str, str] = {}
EFFECTIVE_CONDITION_MAX = 5000  # 코스 수만큼 끝없이 쌓이지 않게(오래된 것부터 버린다)
REGENERATE_RETRIES = 2


def _remember_condition(course_id: str, text: str) -> None:
    _EFFECTIVE_CONDITION.pop(course_id, None)  # 다시 넣어 가장 최근으로
    _EFFECTIVE_CONDITION[course_id] = text
    while len(_EFFECTIVE_CONDITION) > EFFECTIVE_CONDITION_MAX:
        _EFFECTIVE_CONDITION.pop(next(iter(_EFFECTIVE_CONDITION)))


def _effective_condition(course_id: str) -> str | None:
    return _EFFECTIVE_CONDITION.get(course_id) or _last_condition_text(course_id)


def _last_condition_text(course_id: str) -> str | None:
    """직전에 조건을 말한 문장(편집·질문·재생성 요청은 건너뛴다)."""
    from app.pipeline.edit import parse_edit

    for msg in reversed(chat_store.list(course_id)):
        if msg.role != "user":
            continue
        text = msg.text
        # 방금 들어온 요청 자신과 재생성·조건변경·질문 요청은 조건 문장이 아니다
        if (
            _REGENERATE_RE.search(text)
            or _CONDITION_CHANGE_RE.search(text)
            or _REPLACE_ALL_RE.search(text)
            or _ALL_QUALITY_RE.search(text)
            or _is_question(text)
        ):
            continue
        if parse_edit(text).action != "none":
            continue
        if is_actionable(text, parse_constraints(text)):
            return text
    return None


# "시간을 12시로", "예산을 5만원으로 올려줘" — 조건 일부만 바꾸는 요청.
# 이전 조건을 버리면 지역·소요시간 같은 나머지가 통째로 사라진다.
_CONDITION_CHANGE_RE = re.compile(
    r"(?:시간|시각|예산|인원|지역|날짜|이동\s*수단|동선)\s*(?:을|를|은|는)?\s*"
    r"[^\s]*\s*(?:으로|로)?\s*(?:바꿔|바꾸|변경|올려|낮춰|줄여|늘려|해줘)"
)


# "전부 다른 곳으로", "여기 말고 다른 데로" — 조건은 그대로 두고 장소만 갈아 끼운다
# "전부 좀 더 저렴하게", "다 조용한 데로" — 코스 전체의 성격을 바꾸라는 요청.
# 자리를 집지 않았으므로 편집이 아니라 조건 변경으로 다뤄야 한다.
_ALL_QUALITY_RE = re.compile(
    r"(?:전부|모두|전체|싹|다)\s*(?:좀\s*)?(?:더\s*)?"
    r"(?:저렴|싸게|비싸|조용|활기|가까|분위기|실내|야외|고급|캐주얼)"
)
_UNDO_RE = re.compile(
    r"되돌려|되돌리|원래\s*대로|이전\s*(?:코스|걸로|거로)|아까\s*(?:코스|걸로|거로|게\s*나)|실행\s*취소"
)
# 코스별 직전 AI 변경 전 상태(한 단계). 프로세스 메모리 — 재시작하면 사라져도 되는 편의 기능이다.
_UNDO_SNAPSHOT: dict[str, list] = {}
_UNDO_MAX_COURSES = 5000


def _remember_undo(course_id: str, items: list) -> None:
    _UNDO_SNAPSHOT.pop(course_id, None)
    _UNDO_SNAPSHOT[course_id] = items
    while len(_UNDO_SNAPSHOT) > _UNDO_MAX_COURSES:
        _UNDO_SNAPSHOT.pop(next(iter(_UNDO_SNAPSHOT)))


_INSTEAD_RE = re.compile(r"대신|말고")  # "카페 대신 공원" — 규칙 파서가 추가로 오해하던 표현
_REPLACE_ALL_RE = re.compile(
    r"(?:전부|다|모두|싹)\s*다른\s*(?:곳|데|장소)|여기\s*말고\s*다른|비슷한데\s*다른"
)


_QUESTION_RE = re.compile(r"[?？]\s*$|나요|까요|어때|얼마나|있나|없나|맞나|되나|뭐야|어디야")


def _is_question(text: str) -> bool:
    """코스를 바꾸라는 지시가 아니라 물음인지."""
    return bool(_QUESTION_RE.search(text.strip()))


def _edit_reply(
    course: Course,
    action: str,
    old_ids: list[str],
    new_ids: list[str],
    old_names: dict[str, str] | None = None,
) -> str:
    """편집 결과를 무엇이 바뀌었는지로 알린다("3곳으로 구성했어요"는 편집엔 무의미)."""
    names = {it.place.id: it.place.name for it in course.items}
    # 뺀 장소는 이미 코스에 없으므로, 이름은 편집 전 스냅샷에서 찾아야 한다.
    names = {**(old_names or {}), **names}
    added = [pid for pid in new_ids if pid not in old_ids]
    removed = [pid for pid in old_ids if pid not in new_ids]
    n = len(course.items)
    if action == "add" and added:
        return f"'{names.get(added[0], '새 장소')}'를 마지막에 추가했어요. 이제 {n}곳이에요."
    if action == "remove" and removed:
        gone = ", ".join(f"'{names[pid]}'" for pid in removed if pid in names)
        what = gone or "한 곳"
        return f"{what}을 뺐어요. 이제 {n}곳이에요."
    if action == "replace" and added:
        order = new_ids.index(added[0]) + 1
        gone = names.get(removed[0]) if removed else None
        new_name = names.get(added[0], "다른 곳")
        if gone:
            return f"{order}번째를 '{gone}' 대신 '{new_name}'으로 바꿨어요."
        return f"{order}번째를 '{new_name}'으로 바꿨어요."
    return f"수정했어요. 이제 {n}곳이에요."


def _change_note(old_ids: list[str], new_ids: list[str]) -> str:
    """이미 있던 코스를 다시 짰을 때 무엇이 바뀌었는지(다 바뀐 줄 알고 처음부터 다시 보지 않게)."""
    kept = len(set(old_ids) & set(new_ids))
    if new_ids == old_ids:
        return "장소는 그대로예요."
    if kept == len(new_ids) and len(new_ids) < len(old_ids):
        return f"조건에 맞추느라 {len(old_ids) - len(new_ids)}곳을 뺐어요."
    if kept == len(new_ids):
        return "장소는 그대로 두고 순서·시간만 맞췄어요."
    if kept:
        return f"{kept}곳은 그대로 두고 {len(new_ids) - kept}곳을 새로 골랐어요."
    return "모두 새로 골랐어요."


def _ai_reply(
    course: Course,
    relaxed: bool,
    needs_confirmation: bool,
    region_guessed: bool = False,
    constraints: PlanConstraints | None = None,
    pref_region: str | None = None,
    closed_dropped: int = 0,
) -> str:
    n = len(course.items)
    # 폐업·휴무로 뺀 자리는 반드시 말한다 — 말없이 줄이면 "왜 3곳만 줬지"가 된다.
    closed_note = (
        f" 문 닫는 곳 {closed_dropped}곳은 빼고 구성했어요." if closed_dropped else ""
    )
    if needs_confirmation:
        # 왜 부족한지 짚어 줘야 무엇을 바꿀지 알 수 있다("완화할까요?"만으로는 막막하다)
        hour = constraints.start_time.hour if constraints and constraints.start_time else None
        if n == 0 and hour is not None and (hour >= 23 or hour < 6):
            return (
                f"{hour}시에는 문 연 곳을 찾기 어려워요. "
                "시간을 조금 당기거나 다른 지역으로 바꿔 볼까요?"
            )
        if n == 0 and constraints is not None and constraints.budget_max:
            budget = constraints.budget_max
            amount = f"{budget // 10000}만원" if budget >= 10000 else f"{budget:,}원"
            return (
                f"1인 {amount} 안에서 맞는 곳을 찾지 못했어요. "
                "예산을 올리거나 조건을 완화할까요?"
            )
        if n == 0:
            return "조건에 맞는 장소를 찾지 못했어요. 지역이나 시간을 바꿔 볼까요?"
        return f"{n}곳까지만 찾았어요.{closed_note} 조건을 완화할까요?"
    # 무엇을 알아들었는지 먼저 되짚어 준다(잘못 알아들었으면 바로 정정 가능)
    parts: list[str] = []
    if course.plan_date:
        parts.append(f"{course.plan_date.month}월 {course.plan_date.day}일")
    first = course.items[0] if course.items else None
    if first is not None and first.arrive is not None:
        parts.append(f"{first.arrive.strftime('%H:%M')} 시작")
    if constraints is not None and constraints.start_place:
        parts.append(f"{constraints.start_place} 출발")
    prefix = f"{' '.join(parts)}, " if parts else ""
    base = f"{prefix}{n}곳으로 코스를 구성했어요."
    # 언제 끝나는지 미리 알려주면 일정 조정을 바로 할 수 있다
    last = course.items[-1] if course.items else None
    if last is not None and last.depart is not None:
        base += f" {last.depart.strftime('%H:%M')}쯤 마무리돼요."
    if constraints is not None and constraints.prefer_indoor:
        base += " 비 예보라 실내 위주로 골랐어요."
    base += closed_note
    if relaxed:
        base += " 일부 조건은 완화했어요."
    if pref_region:
        # 사용자가 지역을 말하지 않아 선호 설정 값을 썼다는 것을 드러낸다
        base += f" 설정하신 {pref_region} 기준으로 만들었어요."
    if region_guessed:
        # 지역을 못 알아들으면 기본 지역으로 만들어지므로, 조용히 넘어가지 않고 알린다.
        base += f" 지역을 못 알아들어 {course.region or DEFAULT_REGION} 기준으로 만들었어요."
    return base


@chat_router.get("/courses/{course_id}/messages", response_model=list[ChatMessage])
async def get_messages(
    course_id: str,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
    x_together_token: str | None = Header(default=None),
) -> list[ChatMessage]:
    """채팅 로그 조회 (append-only). 생성자와 같이 정하는 상대만 — 공유 링크로는 보이지 않는다."""
    from app.identity import course_editor

    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    course_editor(course, x_user_id, x_user_token, x_together_token)
    return chat_store.list(course_id)

