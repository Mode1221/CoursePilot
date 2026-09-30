"""규칙으로 답하지 못한 코스 질문에 LLM 이 답한다 — 코스에 있는 사실만 근거로.

"이 코스 몇 점짜리야?", "커플한테 괜찮아?" 같은 질문에 늘 같은 요약을 되풀이했다.
LLM 에는 장소 이름·분류·시간·가격·평점·확인된 사실 태그만 준다. 모르는 것(메뉴·예약 등)은
모른다고 답하게 한다 — 지어낸 가게 정보가 가장 위험하다. 키가 없거나 실패하면 None.
"""
from __future__ import annotations

from app.config import settings
from app.schemas import Course

_SYSTEM = (
    "데이트 코스 앱의 도우미. 아래 '코스 사실'에 있는 내용만 근거로 한국어 1~2문장으로 답한다. "
    "사실에 없는 정보(메뉴, 예약, 분위기 세부, 가격 외 수치 등)는 추측하지 말고 "
    "'확인된 정보가 없어요. 방문 전 매장에 확인해 주세요.'라고 답한다. "
    "코스를 바꾸고 싶어 하면 '2번 다른 곳으로'처럼 말하면 바꿀 수 있다고 안내한다."
)
MAX_TOKENS = 200


def course_facts(course: Course) -> str:
    lines = []
    for i, it in enumerate(course.items, 1):
        p = it.place
        bits = [f"{i}. {p.name}", p.category or ""]
        if it.arrive and it.depart:
            bits.append(f"{it.arrive.strftime('%H:%M')}~{it.depart.strftime('%H:%M')}")
        if p.price is not None:
            bits.append(f"1인 {p.price:,}원" + ("(추정)" if p.price_estimated else ""))
        if p.rating is not None and (p.rating_count or 0) >= 30:
            bits.append(f"평점 {p.rating:.1f}({p.rating_count}명)")
        if p.open_time and p.close_time and not p.hours_unverified:
            bits.append(f"영업 {p.open_time.strftime('%H:%M')}~{p.close_time.strftime('%H:%M')}")
        if p.fact_tags:
            bits.append("가능: " + ",".join(p.fact_tags))
        if p.caution_tags:
            bits.append("주의: " + ",".join(p.caution_tags))
        if it.travel_to_next:
            bits.append(f"다음까지 {it.travel_to_next.duration_min}분")
        lines.append(" · ".join(b for b in bits if b))
    return "\n".join(lines)


async def llm_answer(course: Course, question: str) -> str | None:
    from app.metrics import metrics_store

    if not course.items:
        return None
    prompt = f"코스 사실:\n{course_facts(course)}\n\n질문: {question}"
    try:
        text = await _ask(prompt)
    except Exception:
        text = None
    metrics_store.record_external("llm.answer", ok=text is not None)
    return text.strip() if text and text.strip() else None


async def _ask(prompt: str) -> str | None:
    if settings.llm_provider == "openai":
        from app.llm_client import get_openai_client

        client = get_openai_client()
        if client is None:
            return None
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    from app.llm_client import get_anthropic_client

    client = get_anthropic_client()
    if client is None:
        return None
    from app.llm_client import anthropic_params

    resp = await client.messages.create(
        **anthropic_params(MAX_TOKENS, _SYSTEM),
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
