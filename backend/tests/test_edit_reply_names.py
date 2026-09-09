"""편집 결과 안내에 무엇이 빠지고 무엇이 들어왔는지 이름으로 알린다."""
from datetime import time

from app.main import _edit_reply
from app.schemas import Course, Place, TimelineItem


def _course(*names: str) -> Course:
    return Course(
        id="c",
        items=[
            TimelineItem(
                place=Place(id=n, name=n, lat=37.5, lng=127.0),
                arrive=time(12 + i, 0),
                depart=time(13 + i, 0),
            )
            for i, n in enumerate(names)
        ],
    )


def test_뺀_장소_이름을_말한다():
    text = _edit_reply(_course("카페A"), "remove", ["카페A", "술집B"], ["카페A"], {"술집B": "술집B"})
    assert "'술집B'" in text and "1곳" in text


def test_여러_곳을_빼면_모두_말한다():
    text = _edit_reply(
        _course("카페A"), "remove", ["카페A", "B", "C"], ["카페A"], {"B": "B", "C": "C"}
    )
    assert "'B'" in text and "'C'" in text


def test_이름을_모르면_예전처럼_말한다():
    text = _edit_reply(_course("카페A"), "remove", ["카페A", "없어진곳"], ["카페A"])
    assert "한 곳을 뺐어요" in text


def test_교체는_바뀐_양쪽을_말한다():
    text = _edit_reply(
        _course("카페A", "새술집"), "replace", ["카페A", "옛술집"], ["카페A", "새술집"], {"옛술집": "옛술집"}
    )
    assert "'옛술집'" in text and "'새술집'" in text and "2번째" in text


def test_추가는_들어온_곳을_말한다():
    text = _edit_reply(_course("카페A", "새카페"), "add", ["카페A"], ["카페A", "새카페"])
    assert "'새카페'" in text
