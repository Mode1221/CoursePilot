"""공연·전시 일정(KOPIS): 기간 파싱과 날짜 필터."""
from datetime import date

import pytest

from app.adapters.culture import (
    CultureClient,
    Performance,
    drop_finished,
    parse_ymd,
    to_performance,
)

XML = """<?xml version="1.0" encoding="UTF-8"?>
<dbs>
  <db>
    <mt20id>PF1</mt20id><prfnm>봄 전시</prfnm><fcltynm>성수아트홀</fcltynm>
    <prfpdfrom>2026.09.01</prfpdfrom><prfpdto>2026.09.30</prfpdto><genrenm>전시</genrenm>
  </db>
  <db>
    <mt20id>PF2</mt20id><prfnm>지난 공연</prfnm><fcltynm>대학로극장</fcltynm>
    <prfpdfrom>2026.07.01</prfpdfrom><prfpdto>2026.07.31</prfpdto><genrenm>연극</genrenm>
  </db>
</dbs>
"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026.09.01", date(2026, 9, 1)),
        ("20260901", date(2026, 9, 1)),
        ("2026-09-01", date(2026, 9, 1)),
        ("2026.13.01", None),
        ("", None),
        (None, None),
    ],
)
def test_날짜_표기를_흡수한다(raw, expected):
    assert parse_ymd(raw) == expected


def test_기간을_못_읽으면_버린다():
    assert to_performance({"prfnm": "이름만"}) is None
    assert to_performance({"prfpdfrom": "20260930", "prfpdto": "20260901"}) is None


def test_진행_여부를_기간으로_판단한다():
    perf = Performance("1", "전시", "홀", date(2026, 9, 1), date(2026, 9, 30))
    assert perf.runs_on(date(2026, 9, 9))
    assert perf.runs_on(date(2026, 9, 30))
    assert not perf.runs_on(date(2026, 10, 1))


def test_코스_날짜에_안_하는_일정은_제거한다():
    running = Performance("1", "a", "홀", date(2026, 9, 1), date(2026, 9, 30))
    finished = Performance("2", "b", "홀", date(2026, 7, 1), date(2026, 7, 31))
    assert drop_finished([running, finished], date(2026, 9, 9)) == [running]


class _Fake(CultureClient):
    def __init__(self, text):
        self._key = "k"
        self._text = text

    async def performances(self, day, area_code="11", rows=50):
        from app.adapters.culture import _xml_items

        found = [to_performance(i) for i in _xml_items(self._text)]
        return [p for p in found if p and p.runs_on(day)]


async def test_진행_중인_일정만_돌려준다():
    result = await _Fake(XML).performances(date(2026, 9, 9))
    assert [p.id for p in result] == ["PF1"]
    assert result[0].venue == "성수아트홀" and result[0].genre == "전시"


async def test_깨진_XML은_빈_목록():
    assert await _Fake("<not xml").performances(date(2026, 9, 9)) == []


async def test_키가_없으면_조회하지_않는다():
    client = CultureClient()
    client._key = ""
    assert not client.enabled
    assert await client.performances(date(2026, 9, 9)) == []
