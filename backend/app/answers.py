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
# 아직 모으지 않는 정보. 코스 요약으로 얼버무리지 말고 없다고 말한다.
UNKNOWN_FACT_QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("화장실", ("화장실",)),
    ("와이파이", ("와이파이", "wifi", "인터넷")),
    ("흡연", ("흡연", "담배")),
    ("콜키지", ("콜키지", "주류 반입", "와인 반입")),
    ("배달", ("배달", "포장")),
)
_COST_WORDS = ("얼마", "비용", "가격", "예산")
_HOURS_WORDS = ("영업시간", "몇 시까지", "몇시까지", "문 닫", "문닫", "언제까지 해", "브레이크")
# 이동 질문. "이동 시간 얼마나 돼"의 '얼마'가 비용으로 새지 않도록 먼저 본다.
_TRAVEL_WORDS = ("이동", "어떻게 가", "걸어서", "도보로", "지하철", "버스", "택시", "거리")
_WHY_WORDS = ("왜", "이유", "어떻게 골", "근거")
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


# 영업시간은 최대 30일 캐시를 쓴다. 이보다 오래된 값은 "언제 확인했는지"를
# 함께 말해 줘야 사용자가 스스로 판단할 수 있다.
STALE_HINT_DAYS = 7


def _checked_days_ago(place) -> int | None:
    from datetime import UTC, datetime

    checked = place.hours_checked_at
    if checked is None:
        return None
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - checked).days)


def hours_answer(course: Course) -> str:
    """영업시간 질문: 확인된 곳은 시간을, 확인 못 한 곳은 그 사실을 말한다."""
    known, unknown = [], []
    for item in course.items:
        place = item.place
        if place.open_time and place.close_time and not place.hours_unverified:
            line = (
                f"{place.name} {place.open_time.strftime('%H:%M')}~"
                f"{place.close_time.strftime('%H:%M')}"
            )
            # 브레이크는 헛걸음으로 이어지는 정보라 함께 말한다
            if place.break_start and place.break_end:
                line += (
                    f"(브레이크 {place.break_start.strftime('%H:%M')}~"
                    f"{place.break_end.strftime('%H:%M')})"
                )
            days = _checked_days_ago(place)
            if days is not None and days >= STALE_HINT_DAYS:
                line += f" ({days}일 전 확인)"
            known.append(line)
        else:
            unknown.append(place.name)
    parts = []
    if known:
        parts.append(", ".join(known))
    if unknown:
        names = ", ".join(unknown)
        parts.append(f"{names}{_topic_particle(names)} 영업시간을 확인하지 못했어요")
    return ". ".join(parts) + "." if parts else "영업시간 정보가 없어요."


_MODE_NAMES = {"walk": "도보", "car": "차", "transit": "대중교통"}


def travel_answer(course: Course) -> str:
    """구간별 이동 수단·시간으로 답한다."""
    legs = []
    for i, item in enumerate(course.items[:-1]):
        route = item.travel_to_next
        if route is None:
            continue
        mode = _MODE_NAMES.get(getattr(route.mode, "value", str(route.mode)), "이동")
        legs.append(
            f"{item.place.name}→{course.items[i + 1].place.name} {mode} {route.duration_min}분"
        )
    if not legs:
        return "이동 정보가 아직 없어요."
    total = sum(
        it.travel_to_next.duration_min for it in course.items if it.travel_to_next
    )
    return ". ".join([", ".join(legs), f"이동은 모두 {total}분이에요."])


def why_answer(course: Course, text: str) -> str:
    """"왜 골랐어?" — 이미 계산해 둔 근거를 장소별로 한 줄씩 답한다."""
    from app.reasons import course_reasons

    reasons = course_reasons(course, text)
    lines = [
        f"{item.place.name}: {', '.join(reasons[item.place.id])}"
        for item in course.items
        if reasons.get(item.place.id)
    ]
    if not lines:
        return "특별한 조건이 없어서 이동 동선과 시간대에 맞춰 골랐어요."
    return " / ".join(lines)


def unknown_fact_answer(text: str) -> str | None:
    """아직 모으지 않는 정보를 물으면 그렇다고 답한다(요약으로 얼버무리지 않는다)."""
    lowered = (text or "").lower()
    tag = next(
        (tag for tag, words in UNKNOWN_FACT_QUESTIONS if any(w in lowered for w in words)),
        None,
    )
    if tag is None:
        return None
    return f"{tag} 정보는 아직 모으지 않아요. 매장에 직접 확인해 주세요."


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
    unknown = unknown_fact_answer(text)
    if unknown:
        return unknown
    if any(w in text for w in _TRAVEL_WORDS):
        return travel_answer(course)
    if any(w in text for w in _WHY_WORDS):
        return why_answer(course, text)
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


