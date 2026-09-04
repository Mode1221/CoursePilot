"""자연어 → 조건 분해 (7-1 Decomposition).

LLM(Function Calling)이 정석이나, 키가 없을 때를 위한 규칙 기반 폴백 파서를 제공한다.
"""
from __future__ import annotations

import re
from datetime import time

from app.schemas import PlanConstraints, TravelMode

_HOUR_RE = re.compile(r"(오전|오후)?\s*(\d{1,2})\s*시")
_DURATION_RE = re.compile(r"(\d{1,2})\s*시간")
_TRAVEL_RE = re.compile(r"(도보|차량|대중교통)?\s*(\d{1,3})\s*분")
_BUDGET_RE = re.compile(r"(\d+)\s*만\s*원")

_MODE_MAP = {"도보": TravelMode.WALK, "차량": TravelMode.CAR, "대중교통": TravelMode.TRANSIT}
_SOFT_KEYWORDS = ["조용한", "활기찬", "비건", "분위기", "가성비", "뷰", "데이트"]


def parse_constraints(text: str) -> PlanConstraints:
    """규칙 기반 조건 추출. LLM 폴백/오프라인 개발용."""
    c = PlanConstraints()

    # 지역: "성수동", "강남역" 등 (동/역/구 접미사)
    region_m = re.search(r"([가-힣]+(?:동|역|구|읍|면))", text)
    if region_m:
        c.region = region_m.group(1)

    # 시작 시각
    hm = _HOUR_RE.search(text)
    if hm:
        hour = int(hm.group(2))
        if hm.group(1) == "오후" and hour < 12:
            hour += 12
        c.start_time = time(hour, 0)

    # 소요 시간 → 종료 시각
    dm = _DURATION_RE.search(text)
    if dm:
        c.duration_min = int(dm.group(1)) * 60
        if c.start_time:
            end_hour = c.start_time.hour + int(dm.group(1))
            # 자정을 넘기면 시각으로 절단하지 않고 종료 미지정(같은 날 내 열림)으로 둔다.
            if end_hour < 24:
                c.end_time = time(end_hour, c.start_time.minute)

    # 이동수단 + 이동시간 상한
    tm = _TRAVEL_RE.search(text)
    if tm:
        if tm.group(1) in _MODE_MAP:
            c.travel_mode = _MODE_MAP[tm.group(1)]
        c.max_travel_min = int(tm.group(2))

    # 예산 (하드 제약)
    bm = _BUDGET_RE.search(text)
    if bm:
        c.budget_max = int(bm.group(1)) * 10_000

    c.keywords = [k for k in _SOFT_KEYWORDS if k in text]
    return c
