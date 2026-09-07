from app.feedback import FeedbackStore
from app.pipeline.agent import _HARD_KEYWORDS


def test_acceptance_rate():
    fs = FeedbackStore()
    assert fs.acceptance_rate() == 0.5  # 표본 없음 → 기본
    fs.log("c1", "relax_accepted")
    fs.log("c2", "relax_accepted")
    fs.log("c3", "relax_rejected")
    assert abs(fs.acceptance_rate() - (2 / 3)) < 1e-6


def test_hard_keywords_preserved():
    # 식이 제한 키워드는 완화 대상에서 제외되어야 함
    kws = ["조용한", "비건", "가성비"]
    kept = [k for k in kws if k in _HARD_KEYWORDS]
    assert kept == ["비건"]
