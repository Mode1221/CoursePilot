"""우천·아이 동반·휠체어 질문에 코스 요약을 되풀이하지 않는다."""
from app.answers import course_answer
from app.schemas import Course, Place, TimelineItem


def _course(*places: Place) -> Course:
    return Course(id="c1", items=[TimelineItem(place=p) for p in places])


def _place(name: str, category: str = "카페", **kw) -> Place:
    return Place(id=name, name=name, category=category, address="성수동", lat=37.54, lng=127.05, **kw)


def test_야외가_섞이면_어디가_문제인지_짚는다():
    answer = course_answer(_course(_place("성수 카페"), _place("서울숲 공원", "공원")), "비 오면 어떡해?")
    assert "서울숲 공원" in answer
    assert "실내" in answer  # 다시 짜는 방법까지 알려 준다


def test_전부_실내면_그대로_다녀도_된다고_답한다():
    answer = course_answer(_course(_place("성수 카페"), _place("성수 전시", "전시")), "비 오면?")
    assert "야외" in answer and "그대로" in answer


def test_노키즈존은_가능이_아니라_불가로_읽는다():
    answer = course_answer(_course(_place("어른 카페", fact_tags=["노키즈"])), "아기 데려가도 돼?")
    assert "어른 카페" in answer
    assert "어려워요" in answer


def test_노키즈존이_없으면_그렇게_답한다():
    answer = course_answer(_course(_place("성수 카페")), "애기 데려가도 되나요?")
    assert "노키즈존으로 확인된 곳은 없어요" in answer


def test_휠체어_접근은_태그가_있으면_답한다():
    answer = course_answer(_course(_place("성수 카페", fact_tags=["휠체어"])), "휠체어 들어가?")
    assert "성수 카페" in answer and "가능" in answer


def test_코스_요약으로_얼버무리지_않는다():
    answer = course_answer(_course(_place("성수 카페")), "비 오면 어떡해?")
    # 요약(곳 수·시작·끝)을 되풀이하지 않고 우천 여부만 답한다
    assert "곳이에요" not in answer
