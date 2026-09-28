"""이미 코스가 있을 때의 후속 요청을 '직전 조건 + 바뀐 부분'으로 만든다.

채팅은 대화다. "7시에 끝나게", "1시간 늦게", "너무 멀어", "차로 갈게"는 새 코스 요청이 아니라
지금 코스 조건의 일부를 바꾸라는 말이다. 문장만 따로 해석하면 지역·시간이 사라지거나
("지역을 못 알아들어 성수 기준으로…") 조건이 없다며 되묻는다.

규칙: 파서가 알아듣는 표현으로 바꾼 뒤 **바뀐 값을 앞에** 두고 직전 조건을 뒤에 붙인다
(파서는 먼저 나온 값을 잡는다).
"""
from __future__ import annotations

import re
from datetime import time

# (패턴, 파서가 알아듣는 조건 문구)
_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"너무\s*멀|멀어|가까운\s*(?:곳|데)|걷기\s*싫|많이\s*걷|덜\s*걷|이동\s*(?:좀\s*)?줄"), "도보 10분 이내"),
    (re.compile(r"차로|차\s*타고|자차|운전|차\s*가지고"), "자차로"),
    (re.compile(r"대중교통|지하철|버스\s*타"), "대중교통으로"),
    (re.compile(r"비싸|저렴|싸게|가성비|돈\s*(?:좀\s*)?아끼"), "저렴한"),
    (re.compile(r"조용|한적|덜\s*붐비|사람\s*(?:좀\s*)?(?:없|적)"), "조용한"),
    (re.compile(r"비\s*(?:와|온|오)|실내"), "실내"),
)
_END_AT_RE = re.compile(
    r"((?:오전|오후|저녁|밤|낮)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분|\s*반)?)\s*(?:에|까지)?\s*(?:끝나|끝내|마무리|헤어|들어가)"
)
_SHIFT_RE = re.compile(r"(\d+|한|두|세)\s*시간(?:\s*(반))?\s*(늦게|일찍|빨리|먼저)")
_SHIFT_MIN_RE = re.compile(r"(\d+)\s*분\s*(늦게|일찍|빨리|먼저)")
_KOR_NUM = {"한": 1, "두": 2, "세": 3}


def _shift_minutes(text: str) -> int | None:
    m = _SHIFT_RE.search(text)
    if m:
        hours = int(m.group(1)) if m.group(1).isdigit() else _KOR_NUM[m.group(1)]
        minutes = hours * 60 + (30 if m.group(2) else 0)
        return minutes if m.group(3) == "늦게" else -minutes
    m = _SHIFT_MIN_RE.search(text)
    if m:
        return int(m.group(1)) if m.group(2) == "늦게" else -int(m.group(1))
    return None


def _fmt(t: time) -> str:
    # 파서는 "13시 반"은 알아듣지만 "13시 30분"의 30분을 이동 시간으로 읽는다
    return f"{t.hour}시" + (" 반" if t.minute else "")


_TIME_RE = re.compile(
    r"(?:오전|오후|저녁|밤|낮|아침|점심|새벽)?\s*\d{1,2}\s*시(?!간)(?:\s*반|\s*\d{1,2}\s*분)?"
    r"(?:\s*(?:부터|에|쯤|까지|시작))?|아침|점심|저녁|밤|오전|오후|낮"
)
_DATE_RE = re.compile(
    r"오늘|내일|모레|글피|(?:이번|다음|담)\s*주\s*[월화수목금토일]?(?:요일)?|주말|평일"
    r"|[월화수목금토일]요일|\d{1,2}\s*월\s*\d{1,2}\s*일"
)
_DURATION_RE = re.compile(r"\d+\s*시간(?:\s*반)?(?:\s*(?:동안|정도|만))?|반나절|하루\s*종일")


def _drop(previous: str, text: str, pattern: re.Pattern[str]) -> str:
    """새 요청이 같은 종류의 값을 말했으면 직전 조건에서 그 값을 지운다(파서가 옛 값을 잡지 않게)."""
    return pattern.sub(" ", previous) if pattern.search(text) else previous


def followup_text(text: str, previous: str, start: time | None) -> str:
    """후속 요청 + 직전 조건 → 새 조건 문장."""
    parts: list[str] = []
    shift = _shift_minutes(text)
    if shift is not None and start is not None:
        total = max(0, min(23 * 60 + 30, start.hour * 60 + start.minute + shift))
        total = round(total / 30) * 30  # 30분 단위(파서가 읽는 단위)
        parts.append(f"{_fmt(time(total // 60, total % 60))} 시작")
    end = _END_AT_RE.search(text)
    if end:
        parts.append(f"{end.group(1).strip()}까지")
    for pattern, phrase in _PHRASES:
        if pattern.search(text) and phrase not in parts:
            parts.append(phrase)
    if "자차로" in parts or "대중교통으로" in parts:
        # "걷기 싫어 차로 갈게" — 도보 제한이 아니라 이동 수단을 바꾸라는 말이다
        parts = [x for x in parts if x != "도보 10분 이내"]
    rest = text
    for pattern in (_SHIFT_RE, _SHIFT_MIN_RE, _END_AT_RE):
        rest = pattern.sub(" ", rest)
    base = previous
    if shift is not None or _TIME_RE.search(rest):
        base = _TIME_RE.sub(" ", base)  # 시작 시각을 새로 정했다
    base = _drop(base, rest, _DATE_RE)
    # 끝나는 시각을 정했으면 옛 소요 시간은 버린다(둘 다 있으면 서로 어긋난다)
    base = _DURATION_RE.sub(" ", base) if end else _drop(base, rest, _DURATION_RE)
    return re.sub(r"\s+", " ", " ".join([*parts, rest.strip(), base])).strip()
