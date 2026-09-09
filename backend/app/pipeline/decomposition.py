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
# "한 시간", "두 시간 반" 처럼 한글 수사로 말하는 소요 시간
_HANGUL_HOURS = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8}
_HANGUL_DURATION_RE = re.compile(
    r"(?<![가-힣])(한|두|세|네|다섯|여섯|일곱|여덟)\s*시간\s*(반)?"
)
# "퇴근하고", "퇴근 후" → 통상 저녁 7시 시작
_AFTER_WORK_RE = re.compile(r"퇴근\s*(?:하고|후|하면|한\s*뒤|끝나고)")
AFTER_WORK_HOUR = 19
# "저녁 7시부터 10시까지" 같은 범위 표현
_RANGE_RE = re.compile(
    r"(오전|오후|아침|점심|낮|저녁|밤|새벽)?\s*(\d{1,2})\s*시\s*(?:\d{1,2}\s*분)?\s*"
    r"(?:부터|에서|~|-|–)\s*"
    # "11시부터 3시간"은 범위가 아니다 → 뒤에 "간"이 오면 매치하지 않는다
    r"(오전|오후|아침|점심|낮|저녁|밤|새벽)?\s*(\d{1,2})\s*시(?!간)(?:\s*(\d{1,2})\s*분)?\s*(?:까지)?"
)
# 시간 표현 관용구 → 소요 시간(분)
_DURATION_WORDS = {"반나절": 240, "하루 종일": 480, "하루종일": 480}
_TRAVEL_RE = re.compile(r"(도보|차량|대중교통)?\s*(\d{1,3})\s*분")
# "3만원", "3만 5천원" 은 만원, 그 외 "20000원" 은 원 단위
# "3~5만원", "3만원에서 5만원" 처럼 범위를 말하면 상한을 예산으로 본다
_BUDGET_RANGE_RE = re.compile(r"(\d+)\s*(?:만원?)?\s*(?:~|-|–|에서|부터)\s*(\d+)\s*만\s*원")
# "3만원", "3만 5천원", 그리고 원을 생략한 "3만"(1인 3만)도 예산으로 본다
_BUDGET_MAN_RE = re.compile(r"(\d+)\s*만\s*(?:(\d)\s*천)?\s*원?")
_BUDGET_WON_RE = re.compile(r"(\d{4,})\s*원")
# 인원수: "4명", "3인" / 숫자 없이 쓰는 표현도 함께 본다
# "1인당 2만원"의 "1인"은 인원이 아니라 단가 표현이다 → 뒤에 "당"이 오면 제외
_PARTY_RE = re.compile(r"(\d{1,2})\s*(?:명|인)(?!분|당)")
# "술집 빼고", "매운 거 말고" 처럼 제외를 뜻하는 표현
_EXCLUDE_RE = re.compile(
    r"([가-힣]{1,6}?)\s*(?:은|는|을|를|이|가|거|건)?\s*(?:빼고|제외하고|제외|말고|없이)"
)
# "강남역에서 출발", "홍대입구역에서 만나" 처럼 출발지를 지정하는 표현
_START_PLACE_RE = re.compile(
    r"([가-힣A-Za-z0-9]{2,12}?)\s*에서\s*(?:출발|만나|모여|시작)"
)
_STOP_NUM_RE = re.compile(r"(\d)\s*(?:차|군데|곳)")
# 앞에 다른 한글이 붙으면 개수 표현이 아니다("조용한 곳"의 "한 곳")
_STOP_WORD_RES = [
    (re.compile(r"(?<![가-힣])" + pattern), count)
    for pattern, count in [
        (r"한\s*곳", 1), (r"두\s*(?:곳|군데)", 2), (r"세\s*(?:곳|군데)", 3), (r"네\s*(?:곳|군데)", 4),
        (r"다섯\s*(?:곳|군데)", 5), (r"여섯\s*(?:곳|군데)", 6),
    ]
]
_PARTY_WORDS = {"혼자": 1, "둘이": 2, "두명": 2, "셋이": 3, "세명": 3, "넷이": 4, "네명": 4}
# 예산이 "총액"임을 알려주는 표현 (1인 기준으로 나눠서 쓴다)
_TOTAL_BUDGET_WORDS = ("총", "다 해서", "다해서", "전부", "합쳐서", "모두")

# "도보로만", "걸어서만" 처럼 수단을 고정해달라는 표현
_STRICT_MODE_RE = re.compile(r"(?:도보|걸어서|차량|대중교통)\s*로?만|만\s*(?:도보|이동)")
# "비 온대", "우천", "장마" → 실내 위주 대체 코스
_RAIN_RE = re.compile(r"비\s*(?:와|와서|온다|온대|올|오면|오는|맞기)|우천|장마|폭우|비올")
_MODE_MAP = {"도보": TravelMode.WALK, "차량": TravelMode.CAR, "대중교통": TravelMode.TRANSIT}
# 시간 표현 없이 수단만 말하는 경우("지하철로 이동", "택시 타고"). 긴 표현부터 본다.
_MODE_WORD_RES: list[tuple[re.Pattern[str], TravelMode]] = [
    (re.compile(r"대중\s*교통|지하철|전철|버스\s*(?:로|타)|차\s*없이|뚜벅이"), TravelMode.TRANSIT),
    (re.compile(r"자차|자가용|차\s*(?:로|끌|가지)|택시|드라이브|차량"), TravelMode.CAR),
    (re.compile(r"도보|걸어서|걸어\s*갈|걸을"), TravelMode.WALK),
]
_SOFT_KEYWORDS = [
    "조용한", "활기찬", "비건", "채식", "분위기", "가성비", "뷰", "데이트",
    "루프탑", "감성", "이색", "브런치", "노키즈", "반려동물", "주차", "야경", "핫플",
    # 실사용 표현 보강: 날씨·활동 종류를 검색 키워드로 전달한다
    "실내", "야외", "산책", "전시", "공연", "디저트", "사진", "포토",
    "술집", "와인", "카페", "맛집", "코스요리", "오마카세", "한식", "일식", "중식", "양식",
    # 자주 쓰는 표현 보강
    "커피", "베이커리", "빵집", "파스타", "이자카야", "포차", "칵테일", "보드게임", "전시회",
    "애견동반", "펫프렌들리", "휠체어", "배리어프리", "금연", "테라스", "단체석", "룸", "단체",
    # 장소 성격을 그대로 검색어로 쓰는 표현
    "한정식", "노포", "서점", "책", "국밥", "라멘", "떡볶이", "전통주", "루프탑바", "전망",
    # 동반 조건이 붙는 요청의 검색어
    "키즈존", "놀이방", "유아의자", "엘리베이터", "좌식",
    # 차수 요청에서 자주 나오는 음식 종류("1차 고기 2차 맥주")
    "고기", "삼겹살", "곱창", "치킨", "피자", "국밥", "초밥", "맥주", "막걸리", "노래방",
]

# 제외 표현에 붙어 오는 조사 — "술은 빼고" 의 "술은" 을 "술" 로 정규화한다
_PARTICLES = ("은", "는", "을", "를", "이", "가", "도", "만")


# "노키즈존 아닌 곳", "테라스 없는 데" 처럼 키워드 뒤에 붙는 부정 표현
_NEGATION_RE = r"(?:존|석|장)?\s*(?:이|가|은|는)?\s*(?:아닌|아니|없는|없이|말고|빼고|제외)"


def _negated(text: str, keyword: str) -> bool:
    """키워드 바로 뒤에 부정 표현이 붙으면 그 조건은 '원하지 않는다'는 뜻이다."""
    return re.search(re.escape(keyword) + _NEGATION_RE, text) is not None


def _strip_particle(word: str) -> str:
    if len(word) > 1 and word[-1] in _PARTICLES:
        return word[:-1]
    return word

# 동행유형(컨텍스트 신호): 표현 → 정규화 라벨
_COMPANION_MAP = {
    "데이트": [
        "데이트", "여자친구", "남자친구", "여친", "남친", "연인", "썸", "부부", "아내", "남편",
        "애인", "기념일", "소개팅", "맞선", "커플",
    ],
    "회식": ["회식", "단체", "팀", "동료", "술자리", "부서"],
    "가족": [
        "가족", "부모님", "엄마", "아빠", "아이", "아기", "부모", "조부모",
        # 실사용 표현 보강: 아이·어르신 동반은 자리·접근성 조건이 달라진다
        "애들", "애기", "유모차", "어르신", "할머니", "할아버지", "임산부", "조카",
    ],
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
        # 접미사 없이 부르는 서울 주요 지명 보강
        "광화문", "삼각지", "한남", "청량리", "성신여대", "혜화", "대학로", "노량진",
        "신사", "논현", "선릉", "역삼", "교대", "사당", "신림", "구로디지털", "목동",
        "연희", "부암동", "성북동", "송파", "석촌호수", "위례", "미사", "동탄", "수원역",
    ],
    key=len,
    reverse=True,
)


# 시각 없이 "브런치"만 말한 경우의 기본 시작 시각(기본 12시는 브런치 시간대를 벗어난다)
BRUNCH_DEFAULT_HOUR = 11
_BRUNCH_RE = re.compile(r"브런치|브런취|모닝\s*세트|조식")

# 마커 없는 1~7시는 저녁으로 보는 게 한국어 관용("7시에 보자" = 19시).
# 오전을 뜻할 때는 보통 "아침 7시"처럼 마커를 붙인다.
EVENING_DEFAULT_MAX_HOUR = 7
# 다만 이 표현들이 함께 있으면 오전으로 둔다
_MORNING_WORDS = ("브런치", "조식", "아침", "모닝", "해돋이", "일출")


def _to_24h(hour: int, marker: str | None) -> int:
    """12시간제 표현을 24시간제로. 마커가 없으면 입력을 그대로 존중한다.

    "24시", "25시" 같은 표현(자정 넘김)도 들어오므로 항상 0~23 으로 접는다.
    """
    hour %= 24
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
# "다음달 5일", "담달 20일"
_NEXT_MONTH_RE = re.compile(r"(?:다음\s*달|담\s*달|내달)\s*(\d{1,2})\s*일")
_WEEKDAY_RE = re.compile(r"(다음\s*주|담주|이번\s*주)?\s*([월화수목금토일])요일")
_MD_RE = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_RELATIVE_DAYS = {"오늘": 0, "내일": 1, "낼": 1, "모레": 2, "글피": 3}
# "11시까지"처럼 시작만 따로 말하고 종료만 "까지"로 붙이는 표현
_END_ONLY_RE = re.compile(
    r"(오전|오후|아침|점심|낮|저녁|밤|새벽)?\s*(\d{1,2})\s*시(?!간)(?:\s*(\d{1,2})\s*분)?\s*까지"
)
# "이번 주말", "주말에" → 다가오는 토요일 (다음 주말이면 한 주 더)
_WEEKEND_RE = re.compile(r"(다음|담|이번)?\s*(?:주\s*)?주말")


# 접미사(동/역/구/읍/면)로 끝나지만 지명이 아닌 흔한 말들.
# "친구랑 놀 데" 가 지역 "친구" 로 잡혀 엉뚱한 검색어가 되던 문제를 막는다.
_REGION_STOPWORDS = {
    "친구", "여친", "남친", "입구", "출구", "지구", "우동", "라면", "동구",
    "가구", "도구", "기구", "연구", "요구", "욕구", "안구", "지구촌",
}
# "아니면", "하면" 처럼 어미로 끝나는 말(면 접미사 오탐)
_REGION_ENDING_RE = re.compile(r"(?:하|되|이|가|오|보|아니|려|다|라|으|주)면$")


def _looks_like_region_typo(candidate: str) -> bool:
    """지명 접미사로 끝나지만 지명이 아닌 표현인지."""
    return candidate in _REGION_STOPWORDS or bool(_REGION_ENDING_RE.search(candidate))


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

    nm = _NEXT_MONTH_RE.search(text)
    if nm:
        day = int(nm.group(1))
        year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        try:
            return date(year, month, day)
        except ValueError:
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

    weekend = _WEEKEND_RE.search(text)
    if weekend:
        ahead = (5 - today.weekday()) % 7  # 다가오는 토요일
        if ahead == 0:
            ahead = 7
        if weekend.group(1) in ("다음", "담"):  # "이번 주말"은 다가오는 주말
            ahead += 7
        return today + timedelta(days=ahead)
    return None


def parse_constraints(text: str, today: date | None = None) -> PlanConstraints:
    """규칙 기반 조건 추출. LLM 폴백/오프라인 개발용."""
    c = PlanConstraints()
    c.plan_date = _parse_date(text, today or date.today())

    # 지역: "성수동", "강남역" 등 (동/역/구 접미사) → 없으면 접미사 없는 지명 사전
    # 접미사 뒤에 한글이 이어지면 지명이 아니다("반려동물"의 "반려동")
    # 접미사 뒤에 한글이 이어지면 지명이 아니다("반려동물"의 "반려동").
    # 다만 조사가 붙는 경우("성수동에서")는 지명으로 인정한다.
    region_m = next(
        (
            m
            for m in re.finditer(
                r"([가-힣]{1,5}?(?:동|역|구|읍|면))"
                r"(?=$|[^가-힣]|에|으로|로|까지|부터|은|는|이|가|의|랑|와|과)",
                text,
            )
            if not _looks_like_region_typo(m.group(1))
        ),
        None,
    )
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
        elif ampm is None and 1 <= hour <= EVENING_DEFAULT_MAX_HOUR:
            if not any(w in text for w in _MORNING_WORDS):
                hour += 12  # "금요일 7시 회식" → 19시
        c.start_time = time(hour % 24, minute)
    else:
        # 숫자 없이 시간대만 말한 경우
        tod = _TIME_OF_DAY_RE.search(text)
        if tod:
            c.start_time = time(_TIME_OF_DAY[tod.group(1)], 0)
        elif _AFTER_WORK_RE.search(text):
            c.start_time = time(AFTER_WORK_HOUR, 0)
        elif _BRUNCH_RE.search(text):
            # "연남동 브런치" 처럼 시각을 말하지 않으면 기본 12시로 잡혀
            # 브런치 시간대를 벗어난다 → 11시로 시작
            c.start_time = time(BRUNCH_DEFAULT_HOUR, 0)

    # 범위 표현("7시부터 10시까지")이면 종료 시각까지 함께 잡는다
    rm = _RANGE_RE.search(text)
    if rm:
        start_h = _to_24h(int(rm.group(2)), rm.group(1))
        end_h = _end_hour(int(rm.group(4)), rm.group(3), rm.group(1), start_h)
        end_min = int(rm.group(5)) if rm.group(5) else 0
        c.start_time = time(start_h % 24, c.start_time.minute if c.start_time else 0)
        c.end_time = time(end_h % 24, min(end_min, 59))
        span = (end_h * 60 + end_min) - (start_h * 60)
        c.duration_min = span if span > 0 else span + 24 * 60

    # 범위 표현이 없어도 "…11시까지"만 붙는 경우가 흔하다("6시에 만나서 11시까지")
    if not rm and c.start_time is not None and c.end_time is None:
        em = _END_ONLY_RE.search(text)
        if em:
            start_h = c.start_time.hour
            end_h = _to_24h(int(em.group(2)), em.group(1))
            end_min = int(em.group(3)) if em.group(3) else 0
            # 마커가 없으면 시작 이후로 해석한다("6시에 만나서 11시까지" = 23시)
            if not em.group(1) and end_h < 12 and end_h + 12 > start_h:
                end_h += 12
            c.end_time = time(end_h % 24, min(end_min, 59))
            span = (end_h * 60 + end_min) - (start_h * 60 + c.start_time.minute)
            c.duration_min = span if span > 0 else span + 24 * 60

    # 소요 시간 → 종료 시각 (N시간 / N시간 반)
    dm = _DURATION_RE.search(text)
    hm = _HANGUL_DURATION_RE.search(text) if dm is None else None
    if hm is not None and not rm and c.duration_min is None:
        c.duration_min = _HANGUL_HOURS[hm.group(1)] * 60 + (30 if hm.group(2) else 0)
        if c.start_time:
            total = c.start_time.hour * 60 + c.start_time.minute + c.duration_min
            c.end_time = time((total // 60) % 24, total % 60)
    if dm and not rm and c.duration_min is None:
        c.duration_min = int(dm.group(1)) * 60 + (30 if dm.group(2) else 0)
        if c.start_time:
            total = c.start_time.hour * 60 + c.start_time.minute + c.duration_min
            # 자정을 넘겨도 종료 시각을 잡는다(타임라인이 다음 날로 이어지는 것을 지원).
            c.end_time = time((total // 60) % 24, total % 60)

    if c.duration_min is None:
        for word, minutes in _DURATION_WORDS.items():
            if word in text:
                c.duration_min = minutes
                if c.start_time:
                    total = c.start_time.hour * 60 + c.start_time.minute + minutes
                    c.end_time = time((total // 60) % 24, total % 60)
                break

    # 이동수단 + 이동시간 상한
    # 수단만 말한 경우도 반영한다("지하철로", "택시 타고") — 예전엔 전부 도보였다
    for rx, mode in _MODE_WORD_RES:
        if rx.search(text):
            c.travel_mode = mode
            break
    tm = _TRAVEL_RE.search(text)
    if tm:
        if tm.group(1) in _MODE_MAP:
            c.travel_mode = _MODE_MAP[tm.group(1)]
        c.max_travel_min = int(tm.group(2))
    if _STRICT_MODE_RE.search(text):
        c.strict_travel_mode = True
    if _RAIN_RE.search(text):
        c.prefer_indoor = True

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

    # 방문 개수: "2차", "세 군데" 등.
    # "1차 고기 2차 술"처럼 차수를 늘어놓으면 마지막 차수가 곧 장소 수다 —
    # 첫 매치만 보면 2차까지 말한 요청을 1곳짜리 코스로 만든다.
    numbers = [int(n) for n in _STOP_NUM_RE.findall(text)]
    if numbers:
        c.stop_count = max(1, min(max(numbers), 6))
    else:
        c.stop_count = next((n for rx, n in _STOP_WORD_RES if rx.search(text)), None)

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
    seen: list[str] = []
    for m in _EXCLUDE_RE.finditer(text):
        word = _strip_particle(m.group(1))
        if word and word not in seen:
            seen.append(word)
    c.exclude_keywords = seen
    # "술 빼고" 는 "술집"도 함께 빼야 한다 — 부분 일치로 소프트 키워드를 거른다
    matched: list[str] = []
    for k in _SOFT_KEYWORDS:
        if k not in text or any(ex in k or k in ex for ex in seen):
            continue
        if _negated(text, k):  # "노키즈존 아닌 곳" → 검색어가 아니라 제외 조건
            if k not in seen:
                seen.append(k)
            continue
        matched.append(k)
    c.exclude_keywords = seen
    # "산책"이 잡혔으면 그 안에 든 "책"은 별도 키워드가 아니다
    c.keywords = [
        k for k in matched if not any(k != other and k in other for other in matched)
    ]
    if c.prefer_indoor and "실내" not in c.keywords:
        c.keywords.insert(0, "실내")  # 우천이면 실내를 최우선 검색어로

    # "성수동 말고 다른 동네" — 빼달라고 한 지역을 그대로 검색 지역으로 쓰면
    # 요청과 정반대가 된다. 다른 지명이 있으면 그쪽을, 없으면 지역 미지정으로 둔다.
    if c.region and any(ex in c.region or c.region in ex for ex in c.exclude_keywords):
        c.region = next(
            (
                r
                for r in _KNOWN_REGIONS
                if r in text and not any(ex in r or r in ex for ex in c.exclude_keywords)
            ),
            None,
        )
    return c


# 요청으로 볼 만한 최소 신호가 없는 입력("ㅋㅋㅋ", "!!!")을 걸러내기 위한 표현
_INTENT_WORDS = (
    "추천", "코스", "짜줘", "만들어", "가자", "놀", "데이트", "모임", "약속", "먹",
    "마시", "구경", "아무데나", "알아서",
)


def is_actionable(text: str, c: PlanConstraints) -> bool:
    """이 입력으로 코스를 만들어도 되는지. 조건이 하나도 없고 의도 표현도
    없으면(오타·감탄사) 만들지 말고 되묻는 편이 낫다 — 크레딧이 소모되므로."""
    if any(
        v not in (None, [], False)
        for v in (
            c.region, c.start_time, c.end_time, c.duration_min, c.budget_max,
            c.party_size, c.stop_count, c.plan_date, c.companion, c.start_place,
        )
    ):
        return True
    if c.keywords or c.exclude_keywords or c.prefer_indoor:
        return True
    return any(w in text for w in _INTENT_WORDS)
