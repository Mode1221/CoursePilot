"""동행유형 표현 보강 — 사람들은 "회식"이라고 잘 말하지 않는다."""
import pytest

from app.pipeline.decomposition import parse_constraints


@pytest.mark.parametrize(
    "text,expected",
    [
        ("회사 사람들이랑 저녁", "회식"),
        ("팀원들이랑 점심", "회식"),
        ("송년회 장소", "회식"),
        ("워크샵 끝나고 저녁", "회식"),
        ("동아리 모임 10명", "친구"),
        ("친목 도모", "친구"),
        ("애인이랑 기념일", "데이트"),
        ("조부모님 모시고", "가족"),
        ("혼밥 하기 좋은 곳", "혼자"),
    ],
)
def test_동행유형을_읽는다(text, expected):
    assert parse_constraints(text).companion == expected


def test_동행_표현이_없으면_비운다():
    assert parse_constraints("성수동 카페").companion is None


def test_인원수와_함께_읽는다():
    c = parse_constraints("동아리 모임 10명")
    assert (c.companion, c.party_size) == ("친구", 10)
