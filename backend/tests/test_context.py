from datetime import time

from app.pipeline.decomposition import parse_constraints
from app.pipeline.planner import desired_slots, score_place
from app.schemas import Place, PlanConstraints


def test_companion_parsed():
    assert parse_constraints("여자친구랑 성수동 데이트").companion == "데이트"
    assert parse_constraints("팀 회식 강남 3시간").companion == "회식"
    assert parse_constraints("부모님 모시고 한정식").companion == "가족"
    assert parse_constraints("성수동 3시간 코스").companion is None


def test_template_varies_by_companion():
    hoesik = desired_slots(PlanConstraints(duration_min=180, companion="회식"))
    assert "bar" in hoesik  # 회식은 술 포함
    family = desired_slots(PlanConstraints(duration_min=180, companion="가족"))
    assert "bar" not in family  # 가족은 술 배제
    date3 = desired_slots(PlanConstraints(duration_min=270, companion="데이트"))
    assert date3[-1] == "activity"  # 데이트는 활동 마무리(3슬롯)


def test_companion_scoring_nudge():
    c = PlanConstraints(companion="데이트")
    romantic = Place(id="r", name="루프탑 뷰 레스토랑", category="restaurant", lat=37.5, lng=127.0)
    plain = Place(id="p", name="백반집", category="restaurant", lat=37.5, lng=127.0)
    assert score_place(romantic, c, None) > score_place(plain, c, None)


def test_evening_family_no_bar():
    slots = desired_slots(PlanConstraints(duration_min=180, companion="가족", start_time=time(19, 0)))
    assert "bar" not in slots