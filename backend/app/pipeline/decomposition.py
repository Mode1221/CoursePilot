"""자연어 → 조건 분해 (7-1 Decomposition).

LLM(Function Calling)이 정석이나, 키가 없을 때를 위한 규칙 기반 폴백 파서를 제공한다.
"""
from __future__ import annotations

import re
from datetime import date, time, timedelta

from app.schemas import PlanConstraints, TravelMode

# "5시간"의 '시'를 시각으로 오인하지 않도록 뒤에 '간'이 오면 제외.
# 분("1시 30분") / 반("1시반") 도 함께 캡처.
_HOUR_RE = re.compile(
    r"(오전|오후|아침|점심|낮|저녁|밤|새벽)?\s*(\d{1,2})\s*시(?!간)\s*(?:(\d{1,2})\s*분|(반))?"
)
# 시각 없이 시간대만 말한 경우("저녁에 홍대")의 기본 시작 시각
_TIME_OF_DAY = {"새벽": 6, "아침": 9, "점심": 12, "낮": 13, "오후": 14, "저녁": 18, "밤": 20}
_TIME_OF_DAY_RE = re.compile(r"(새벽|아침|점심|낮|오후|저녁|밤)")
# 12시간제에서 오후로 해석해야 하는 표현
_PM_WORDS = {"오후", "저녁", "밤", "낮"}
_DURATION_RE = re.compile(r"(\d{1,2})\s*시간\s*(반)?")
# "저녁 7시부터 10시까지" 같은 범위 표현
_RANGE_RE = re.compile(
    r"(오전|오후|아침|점심|낮|저녁|밤|새벽)?\s*(\d{1,2})\s*시\s*(?:\d{1,2}\s*분)?\s*"
    r"(?:부터|에서|~|-|–)\s*"
    r"(오전|오후|아침|점심|낮|저녁|밤|새벽)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?\s*(?:까지)?"
)
# 시간 표현 관용구 → 소요 시간(분)
_DURATION_WORDS = {"반나절": 240, "하루 종일": 480, "하루종일": 480}
_TRAVEL_RE = re.compile(r"(도보|차량|대중교통)?\s*(\d{1,3})\s*분")
# "3만원", "3만 5천원" 은 만원, 그 외 "20000원" 은 원 단위
# "3~5만원", "3만원에서 5만원" 처럼 범위를 말하면 상한을 예산으로 본다
_BUDGET_RANGE_RE = re.compile(r"(\d+)\s*(?:만원?)?\s*(?:~|-|–|에서|부터)\s*(\d+)\s*만\s*원")
_BUDGET_MAN_RE = re.compile(r"(\d+)\s*만\s*(?:(\d)\s*천)?\s*원")
_BUDGET_WON_RE = re.compile(r"(\d{4,})\s*원")
# 인원수: "4명", "3인" / 숫자 없이 쓰는 표현도 함께 본다
_PARTY_RE = re.compile(r"(\d{1,2})\s*(?:명|인)(?!분)")
# "술집 빼고", "매운 거 말고" 처럼 제외를 뜻하는 표현
_EXCLUDE_RE = re.compile(
    r"([가-힣]{2,6}?)\s*(?:은|는|을|를|이|가|거|건)?\s*(?:빼고|제외하고|제외|말고|없이)"
)
# "강남역에서 출발", "홍대입구역에서 만나" 처럼 출발지를 지정하는 표현
_START_PLACE_RE = re.compile(
    r"([가-힣A-Za-z0-9]{2,12}?)\s*에서\s*(?:출발|만나|모여|시작)"
)
_STOP_NUM_RE = re.compile(r"(\d)\s*(?:차|군데|곳)")
_STOP_WORDS = {"한 곳": 1, "한곳": 1, "두 곳": 2, "두곳": 2, "두 군데": 2, "세 곳": 3, "세곳": 3, "세 군데": 3, "네 곳": 4, "네곳": 4}
_PARTY_WORDS = {"혼자": 1, "둘이": 2, "두명": 2, "셋이": 3, "세명": 3, "넷이": 4, "네명": 4}
# 예산이 "총액"임을 알려주는 표현 (1인 기준으로 나눠서 쓴다)
_TOTAL_BUDGET_WORDS = ("총", "다 해서", "다해서", "전부", "합쳐서", "모두")

# "도보로만", "걸어서만" 처럼 수단을 고정해달라는 표현
_STRICT_MODE_RE = re.compile(r"(?:도보|걸어서|차량|대중교통)\s*로?만|만\s*(?:도보|이동)")
_MODE_MAP = {"도보": TravelMode.WALK, "차량": TravelMode.CAR, "대중교통": TravelMode.TRANSIT}
_SOFT_KEYWORDS = [
    "조용한", "활기찬", "비건", "채식", "분위기", "가성비", "뷰", "데이트",
    "루프탑", "감성", "이색", "브런치", "노키즈", "반려동물", "주차", "야경", "핫플",
    # 실사용 표현 보강: 날씨·활동 종류를 검색 키워드로 전달한다
    "실내", "야외", "산책", "전시", "공연", "디저트", "사진", "포토",
    "술집", "와인", "카페", "맛집", "코스요리", "오마카세", "한식", "일식", "중식", "양식",
]

# 동행유형(컨텍스트 신호): 표현 → 정규화 라벨
_COMPANION_MAP = {
    "데이트": ["데이트", "여자친구", "남자친구", "여친", "남친", "연인", "썸", "부부", "아내", "남편"],
    "회식": ["회식", "단체", "팀", "동료", "술자리", "부서"],
    "가족": ["가족", "부모님", "엄마", "아빠", "아이", "아기", "부모", "조부모"],
    "친구": ["친구", "친구들", "동창", "친구랑"],
    "혼자": ["혼자", "혼밥", "혼술", "나홀로"],
}


# 접미사(동/역/구…) 없이 부르는 지명. 사용자가 "홍대에서" 라고 쓰면 지역을 놓치고
# 기본 지역으로 코스를 만들어 버리던 문제를 막는다. 긴 이름부터 매칭한다.
_KNOWN_REGIONS = sorted(
    [
        "홍대", "강남", "신촌", "이태원", "연남", "성수", "망원", "합정", "상수", "서촌",
        "북촌", "익선", "을지로", "종로", "명동", "여의도", "잠실", "건대", "왕십리",
        "가로수길", "압구정", "청담", "삼청동", "송리단길", "문래", "영등포", "샤로수길",
        "서면", "해운대", "광안리", "전포", "동성로", "수성못", "구도심", "봉선동",
        "판교", "정자", "서현", "일산", "라페스타", "송도", "구월동",
    ],
    key=len,
    reverse=True,
)


def _to_24h(hour: int, marker: str | None) -> int:
    """12시간제 표현을 24시간제로. 마커가 없으면 입력을 그대로 존중한다."""
    if marker in _PM_WORDS and hour < 12:
        return hour + 12
    if marker in ("오전", "아침") and hour == 12:
        return 0
    return hour


def _end_hour(hour: int, marker: str | None, start_marker: str | None, start_h: int) -> int:
    """종료 시각 해석. 표시가 없으면 시작의 시간대를 물려받되,
    그렇게 하면 구간이 거꾸로 되는 경우("밤 10시부터 1시까지")에는 물려받지 않는다.
    """
    if marker:
        return _to_24h(hour, marker)
    inherited = _to_24h(hour, start_marker)
    if inherited > start_h:
        return inherited
    return hour  # 자정을 넘긴 것으로 보고 그대로(다음 날) 해석


_WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
_WEEKDAY_RE = re.compile(r"(다음\s*주|담주|이번\s*주)?\s*([월화수목금토일])요일")
_MD_RE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_RELATIVE_DAYS = {"오늘": 0, "내일": 1, "낼": 1, "모레": 2, "글피": 3}


def _parse_date(text: str, today: date) -> date | None:
    """"내일", "이번 주 토요일", "12월 3일" 등에서 날짜를 뽑는다. 없으면 None."""
    md = _MD_RE.search(text)
    if md:
        month, day = int(md.group(1)), int(md.group(2))
        for year in (today.year, today.year + 1):
            try:
                cand = date(year, month, day)
            except ValueError:
                return None
            if cand >= today:  # 이미 지난 날짜면 내년으로 본다
                return cand
        return None

    wm = _WEEKDAY_RE.search(text)
    if wm:
        target = _WEEKDAYS[wm.group(2)]
        ahead = (target - today.weekday()) % 7
        if ahead == 0:
            ahead = 7  # 같은 요일이면 다음 번 그 요일
        if wm.group(1) and "이번" not in wm.group(1):
            ahead += 7
        return today + timedelta(days=ahead)

    for word, offset in _RELATIVE_DAYS.items():
        if word in text:
            return today + timedelta(days=offset)
    return None


def parse_constraints(text: str, today: date | None = None) -> PlanConstraints:
    """규칙 기반 조건 추출. LLM 폴백/오프라인 개발용."""
    c = PlanConstraints()
    c.plan_date = _parse_date(text, today or date.today())

    # 지역: "성수동", "강남역" 등 (동/역/구 접미사) → 없으면 접미사 없는 지명 사전
    region_m = re.search(r"([가-힣]+(?:동|역|구|읍|면))", text)
    if region_m:
        c.region = region_m.group(1)
    else:
        c.region = next((r for r in _KNOWN_REGIONS if r in text), None)

    # 출발지("강남역에서 출발") → 동선 시작점. 지역이 없으면 출발지를 지역으로도 쓴다.
    sp = _START_PLACE_RE.search(text)
    if sp:
        c.start_place = sp.group(1)
        if not c.region:
            c.region = c.start_place

    # 시작 시각 (분/반 포함)
    hm = _HOUR_RE.search(text)
    if hm:
        hour = int(hm.group(2))
        ampm = hm.group(1)
        minute = 30 if hm.group(4) else (int(hm.group(3)) if hm.group(3) else 0)
        minute = min(minute, 59)
        if ampm in _PM_WORDS and hour < 12:
            hour += 12  # "저녁 7시" → 19시 (기존에는 07시로 잘못 해석)
        elif ampm in ("오전", "아침") and hour == 12:
            hour = 0  # 오전 12시 = 자정
        c.start_time = time(hour % 24, minute)
    else:
        # 숫자 없이 시간대만 말한 경우
        tod = _TIME_OF_DAY_RE.search(text)
        if tod:
            c.start_time = time(_TIME_OF_DAY[tod.group(1)], 0)

    # 범위 표현("7시부터 10시까지")이면 종료 시각까지 함께 잡는다
    rm = _RANGE_RE.search(text)
    if rm:
        start_h = _to_24h(int(rm.group(2)), rm.group(1))
        end_h = _end_hour(int(rm.group(4)), rm.group(3), rm.group(1), start_h)
        end_min = int(rm.group(5)) if rm.group(5) else 0
        c.start_time = time(start_h, c.start_time.minute if c.start_time else 0)
        c.end_time = time(end_h % 24, min(end_min, 59))
        span = (end_h * 60 + end_min) - (start_h * 60)
        c.duration_min = span if span > 0 else span + 24 * 60

    # 소요 시간 → 종료 시각 (N시간 / N시간 반)
    dm = _DURATION_RE.search(text)
    if dm and not rm:
        c.duration_min = int(dm.group(1)) * 60 + (30 if dm.group(2) else 0)
        if c.start_time:
            total = c.start_time.hour * 60 + c.start_time.minute + c.duration_min
            # 자정을 넘기면 시각으로 절단하지 않고 종료 미지정(같은 날 내 열림)으로 둔다.
            if total < 24 * 60:
                c.end_time = time(total // 60, total % 60)

    if c.duration_min is None:
        for word, minutes in _DURATION_WORDS.items():
            if word in text:
                c.duration_min = minutes
                if c.start_time:
                    total = c.start_time.hour * 60 + c.start_time.minute + minutes
                    if total < 24 * 60:
                        c.end_time = time(total // 60, total % 60)
                break

    # 이동수단 + 이동시간 상한
    tm = _TRAVEL_RE.search(text)
    if tm:
        if tm.group(1) in _MODE_MAP:
            c.travel_mode = _MODE_MAP[tm.group(1)]
        c.max_travel_min = int(tm.group(2))
    if _STRICT_MODE_RE.search(text):
        c.strict_travel_mode = True

    # 예산 (하드 제약): 범위 → 만원 단위 → 원 단위 순으로 본다
    br = _BUDGET_RANGE_RE.search(text)
    bm = _BUDGET_MAN_RE.search(text)
    if br:
        c.budget_max = int(br.group(2)) * 10_000  # 범위의 상한을 예산으로
    elif bm:
        c.budget_max = int(bm.group(1)) * 10_000 + (int(bm.group(2)) * 1_000 if bm.group(2) else 0)
    else:
        wm = _BUDGET_WON_RE.search(text)
        if wm:
            c.budget_max = int(wm.group(1))

    # 방문 개수: "2차", "세 군데" 등
    sm = _STOP_NUM_RE.search(text)
    if sm:
        c.stop_count = max(1, min(int(sm.group(1)), 6))
    else:
        c.stop_count = next((n for w, n in _STOP_WORDS.items() if w in text), None)

    # 인원수
    pm = _PARTY_RE.search(text)
    if pm:
        c.party_size = max(1, min(int(pm.group(1)), 50))
    else:
        c.party_size = next((n for w, n in _PARTY_WORDS.items() if w in text), None)

    # "4명이서 총 20만원" 처럼 총액을 말한 경우 1인 예산으로 환산한다
    if c.budget_max and c.party_size and c.party_size > 1:
        if any(w in text for w in _TOTAL_BUDGET_WORDS):
            c.budget_max = c.budget_max // c.party_size

    # 동행유형(컨텍스트)
    for label, exprs in _COMPANION_MAP.items():
        if any(e in text for e in exprs):
            c.companion = label
            break

    # 제외 조건: "술집 빼고" → 해당 표현은 소프트 키워드에서 빼고 감점 대상으로 남긴다
    c.exclude_keywords = [m.group(1) for m in _EXCLUDE_RE.finditer(text)]
    excluded = set(c.exclude_keywords)
    c.keywords = [k for k in _SOFT_KEYWORDS if k in text and k not in excluded]
    return c
