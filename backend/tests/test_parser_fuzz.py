"""파서 견고성 — 어떤 입력도 예외로 500 을 만들지 않는다."""
from __future__ import annotations

import random
from datetime import time

from app.pipeline.decomposition import parse_constraints
from app.pipeline.edit import parse_edit

_FRAGMENTS = [
    "성수동", "오후 3시", "2명", "비 와서", "술집 빼고", "3만원", "마지막", "두번째",
    "순서 바꿔", "다 지워", "브런치", "내일", "토요일", "도보로만", "2차까지", "혼자",
    "1번", "까지", "부터", "에서", "!!", "???", "ㅋㅋ", "", '"', "\\",
    "10시부터 2시간", "24시", "25시", "0시", "99명", "-5000원", "12시 30분", "반",
]


def test_무작위_조합에도_예외가_없다():
    rng = random.Random(20260909)
    for _ in range(3000):
        text = " ".join(rng.choice(_FRAGMENTS) for _ in range(rng.randint(1, 7)))
        parse_constraints(text)
        parse_edit(text)


def test_자정을_넘긴_시각_표기를_접는다():
    c = parse_constraints("24시부터 3시간 성수동")
    assert c.start_time == time(0, 0)
    assert c.end_time == time(3, 0)
    assert parse_constraints("25시에 만나자").start_time == time(1, 0)
