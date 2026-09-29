"""코스를 iCalendar(.ics)로 내보내기.

각 장소를 하나의 VEVENT 로 만든다. 도착/출발 시각이 없는 장소는 건너뛴다.
외부 라이브러리 없이 RFC 5545 최소 형식으로 직접 생성한다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.schemas import Course, TravelMode

PRODID = "-//CoursePilot//KO"
ALARM_MINUTES_BEFORE = 30  # 첫 장소 도착 30분 전 알림
# 구간마다 수단이 다를 수 있으므로(도보/대중교통 혼합) 설명에 함께 적는다
_MODE_LABEL = {TravelMode.WALK: "도보", TravelMode.CAR: "차량", TravelMode.TRANSIT: "대중교통"}


def _escape(text: str) -> str:
    """RFC 5545 텍스트 이스케이프(역슬래시·콤마·세미콜론·개행)."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """75옥텟 초과 라인을 접는다(연속 줄은 공백으로 시작)."""
    raw = line.encode("utf-8")
    if len(raw) <= 73:
        return line
    chunks, current = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        if len(current) + len(enc) > 73:
            chunks.append(current.decode("utf-8"))
            current = b""
        current += enc
    chunks.append(current.decode("utf-8"))
    return "\r\n ".join(chunks)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def to_ics(course: Course, day: date | None = None, now: datetime | None = None) -> str:
    """코스를 .ics 문자열로. day 미지정이면 오늘 기준(로컬 시각, 부동 시간)."""
    day = day or date.today()
    now = now or datetime.now()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
    ]
    prev_start: datetime | None = None
    offset_days = 0
    for i, item in enumerate(course.items):
        if item.arrive is None or item.depart is None:
            continue
        start = datetime.combine(day, item.arrive) + timedelta(days=offset_days)
        if prev_start and start < prev_start:  # 자정을 넘긴 일정
            offset_days += 1
            start += timedelta(days=1)
        prev_start = start

        end = datetime.combine(start.date(), item.depart)
        if end <= start:
            end += timedelta(days=1)

        lines += [
            "BEGIN:VEVENT",
            f"UID:{course.id}-{i}@coursepilot",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART:{_stamp(start)}",
            f"DTEND:{_stamp(end)}",
            _fold(f"SUMMARY:{_escape(item.place.name)}"),
        ]
        if item.place.address:
            lines.append(_fold(f"LOCATION:{_escape(item.place.address)}"))
        # 캘린더 앱에서 바로 지도를 열 수 있도록 좌표를 넣는다
        lines.append(f"GEO:{item.place.lat};{item.place.lng}")
        if item.travel_to_next:
            mode = _MODE_LABEL.get(item.travel_to_next.mode, "이동")
            lines.append(
                _fold(
                    f"DESCRIPTION:다음 장소까지 {mode} {item.travel_to_next.duration_min}분"
                )
            )
        if i == 0:
            # 첫 장소만 알림(모든 칸에 알림이 울리면 성가시다).
            # VALARM 은 VEVENT 의 하위 컴포넌트이므로 속성들을 모두 쓴 뒤 마지막에 넣는다
            # (속성 사이에 끼면 무시하거나 파싱에 실패하는 캘린더 앱이 있다).
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"TRIGGER:-PT{ALARM_MINUTES_BEFORE}M",
                _fold(f"DESCRIPTION:{_escape(course.title)} 곧 시작해요"),
                "END:VALARM",
            ]
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
