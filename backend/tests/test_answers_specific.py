"""코스 질문에 딱 맞게 답한다 — 모르면 요약으로 얼버무리지 않고 LLM 또는 '모른다'로."""
from datetime import time
from types import SimpleNamespace

from app.answers import HELP_TEXT, course_answer_summary, specific_answer
from app.pipeline.llm_answer import course_facts, llm_answer
from app.schemas import Course, Place, TimelineItem


def _course() -> Course:
    a = Place(id="a", name="밥집A", category="음식점 > 한식", lat=37.5, lng=127.0, price=20000)
    b = Place(id="b", name="카페B", category="음식점 > 카페", lat=37.5, lng=127.0, price=8000,
              open_time=time(10), close_time=time(22))
    return Course(id="c", items=[
        TimelineItem(place=a, arrive=time(12), depart=time(13, 30)),
        TimelineItem(place=b, arrive=time(13, 45), depart=time(14, 45)),
    ])


def test_순번으로_지목한_자리를_소개한다():
    assert specific_answer(_course(), "2번째 어디야?").startswith("2번째는 카페B")
    assert specific_answer(_course(), "마지막 어떤 곳이야?").startswith("2번째는 카페B")


def test_성격으로_지목하면_조사가_붙어도_찾는다():
    assert specific_answer(_course(), "카페는 얼마야?") == "1인 약 8,000원 예상이에요."
    assert "카페B 10:00~22:00" in specific_answer(_course(), "카페는 몇 시까지 해?")


def test_끝나는_시각은_짧게():
    assert specific_answer(_course(), "몇 시에 끝나?") == "12:00에 시작해 14:45쯤 끝나요."


def test_모으지_않는_정보는_모른다고():
    assert "메뉴 정보는 아직 모으지 않아요" in specific_answer(_course(), "카페 메뉴 뭐 있어?")


def test_고칠_수_있냐고_물으면_방법을_알려준다():
    assert specific_answer(_course(), "바꿔줄 수 있어?") == HELP_TEXT


def test_규칙으로_못_답하면_None():
    assert specific_answer(_course(), "이 코스 몇 점짜리야?") is None


class _Fake:
    def __init__(self):
        self.messages = self
        self.prompt = ""

    async def create(self, **kw):
        self.prompt = kw["messages"][0]["content"]
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=" 가볍게 걷기 좋은 코스예요. ")])


async def test_LLM_답은_코스_사실만_받는다(monkeypatch):
    fake = _Fake()
    monkeypatch.setattr("app.llm_client.get_anthropic_client", lambda: fake)
    assert await llm_answer(_course(), "커플한테 괜찮아?") == "가볍게 걷기 좋은 코스예요."
    assert "카페B" in fake.prompt and "영업 10:00~22:00" in fake.prompt


async def test_키가_없으면_None():
    assert await llm_answer(_course(), "커플한테 괜찮아?") is None


def test_사실_목록():
    facts = course_facts(_course())
    assert facts.splitlines()[0].startswith("1. 밥집A")
    assert course_answer_summary(_course()).startswith("지금 코스는 2곳")
