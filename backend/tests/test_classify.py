

def test_네이버_카테고리_표기를_분류한다():
    from app.pipeline.planner import classify
    from app.schemas import Place

    def _p(cat: str) -> Place:
        return Place(id=cat, name=cat, category=cat, lat=37.5, lng=127.0)

    assert classify(_p("음식점>양식>이탈리아음식")) == "meal"
    assert classify(_p("술집>이자카야")) == "bar"
    assert classify(_p("문화,예술>영화관")) == "activity"
    assert classify(_p("카페,디저트>베이커리")) == "cafe"


def test_이자카야는_술집_체류시간을_쓴다():
    from app.pipeline.validation import stay_minutes
    from app.schemas import Place

    izakaya = Place(id="i", name="i", category="술집>이자카야", lat=37.5, lng=127.0)
    assert stay_minutes(izakaya) == 120


def test_예술은_술집으로_보지_않는다():
    from app.pipeline.planner import classify
    from app.schemas import Place

    art = Place(id="a", name="현대미술관", category="문화,예술>미술관", lat=37.5, lng=127.0)
    assert classify(art) == "activity"
