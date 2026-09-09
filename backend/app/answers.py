"""코스 질문에 대한 답변 생성.

"주차 되나요?"에 코스 요약을 되풀이하지 않도록, 질문 유형별로 답을 만든다.
저장된 사실 태그·가격·영업시간만 쓰고 외부 호출은 하지 않는다.
"""
from __future__ import annotations

from app.schemas import Course

# 질문에 자주 나오는 사실 축 → 장소 태그와 맞춰 본다
_FACT_QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("주차", ("주차", "차 가지고", "차로")),
    ("단체석", ("단체", "룸", "몇 명까지")),
    ("반려동물", ("반려동물", "강아지", "애견")),
    ("콘센트", ("콘센트", "노트북", "카공")),
    ("웨이팅", ("웨이팅", "줄", "대기")),
    ("예약", ("예약",)),
)
_COST_WORDS = ("얼마", "비용", "가격", "예산")
_HOURS_WORDS = ("영업시간", "몇 시까지", "몇시까지", "문 닫", "문닫", "언제까지 해", "브레이크")
_TIME_WORDS = ("몇 시", "언제", "얼마나 걸", "소요", "끝나")


def fact_answer(course: Course, text: str) -> str | None:
    """"주차 되나요?" 처럼 사실을 묻는 질문에 태그로 답한다(모르면 모른다고)."""
    tag = next(
        (tag for tag, words in _FACT_QUESTIONS if any(w in text for w in words)), None
    )
    if tag is None:
        return None
    yes = [it.place.name for it in course.items if tag in it.place.fact_tags]
    no = [it.place.name for it in course.items if tag in it.place.caution_tags]
    if not yes and not no:
        return f"{tag} 정보는 확인되지 않았어요. 방문 전 매장에 확인해 주세요."
    parts = []
    if yes:
        names = ", ".join(yes)
        parts.append(f"{names}{_topic_particle(names)} {tag} 가능해요")
    if no:
        names = ", ".join(no)
        parts.append(f"{names}{_topic_particle(names)} {tag}{_subject_particle(tag)} 어려울 수 있어요")
    return ". ".join(parts) + "."


def _has_final_consonant(word: str) -> bool:
    """마지막 글자에 받침이 있는지(조사 선택용)."""
    last = (word or "").strip()[-1:]
    if not last or not ("가" <= last <= "힣"):
        return False
    return (ord(last) - 0xAC00) % 28 != 0


def _topic_particle(word: str) -> str:
    return "은" if _has_final_consonant(word) else "는"


def _subject_particle(word: str) -> str:
    return "이" if _has_final_consonant(word) else "가"


def hours_answer(course: Course) -> str:
    """영업시간 질문: 확인된 곳은 시간을, 확인 못 한 곳은 그 사실을 말한다."""
    known, unknown = [], []
    for item in course.items:
        place = item.place
        if place.open_time and place.close_time and not place.hours_unverified:
            known.append(
                f"{place.name} {place.open_time.strftime('%H:%M')}~"
                f"{place.close_time.strftime('%H:%M')}"
            )
        else:
            unknown.append(place.name)
    parts = []
    if known:
        parts.append(", ".join(known))
    if unknown:
        names = ", ".join(unknown)
        parts.append(f"{names}{_topic_particle(names)} 영업시간을 확인하지 못했어요")
    return ". ".join(parts) + "." if parts else "영업시간 정보가 없어요."


def cost_answer(course: Course) -> str:
    """비용 질문: 아는 것만 더하고, 추정이 섞였는지 밝힌다."""
    priced = [it.place for it in course.items if it.place.price is not None]
    if not priced:
        return "가격 정보가 없는 곳들이라 예상 비용을 계산하기 어려워요."
    total = sum(p.price for p in priced)
    suffix = " (추정 포함)" if any(p.price_estimated for p in priced) else ""
    unknown = len(course.items) - len(priced)
    tail = f" {unknown}곳은 가격 정보가 없어요." if unknown else ""
    return f"1인 약 {total:,}원 예상이에요{suffix}.{tail}"


def course_answer(course: Course, text: str = "") -> str:
    """질문에 답한다. 사실·비용을 물으면 그것으로, 아니면 코스 요약으로."""
    fact = fact_answer(course, text)
    if fact:
        return fact
    if any(w in text for w in _HOURS_WORDS):
        return hours_answer(course)
    # "얼마나 걸려"는 비용이 아니라 시간을 묻는 말이다 — 시간 표현을 먼저 본다.
    if any(w in text for w in _TIME_WORDS):
        return course_answer_summary(course)
    if any(w in text for w in _COST_WORDS):
        return cost_answer(course)
    return course_answer_summary(course)


def course_answer_summary(course: Course) -> str:
    """지금 코스로 답할 수 있는 것(개수·시작·종료·이동)을 요약해 답한다."""
    n = len(course.items)
    first, last = course.items[0], course.items[-1]
    travel = sum(it.travel_to_next.duration_min for it in course.items if it.travel_to_next)
    parts = [f"지금 코스는 {n}곳이에요"]
    if first.arrive and last.depart:
        parts.append(
            f"{first.arrive.strftime('%H:%M')}에 시작해 {last.depart.strftime('%H:%M')}쯤 끝나요"
        )
    if travel:
        parts.append(f"이동은 모두 {travel}분")
    return (
        ". ".join(parts)
        + ". 장소별 영업시간·리뷰는 카드를 누르면 볼 수 있어요."
    )


