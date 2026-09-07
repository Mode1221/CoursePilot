from app.outcome import OutcomeStore


def test_separation_needs_both_classes():
    os_ = OutcomeStore()
    assert os_.separation() is None
    os_.record(5.0, liked=True)
    assert os_.separation() is None  # 불만족 표본 없음
    os_.record(2.0, liked=False)
    # 만족 평균 5.0 − 불만족 평균 2.0 = 3.0 → 목적함수가 만족을 잘 예측
    assert abs(os_.separation() - 3.0) < 1e-6


def test_separation_averages():
    os_ = OutcomeStore()
    os_.record(4.0, liked=True)
    os_.record(6.0, liked=True)   # 만족 평균 5.0
    os_.record(3.0, liked=False)  # 불만족 평균 3.0
    assert abs(os_.separation() - 2.0) < 1e-6
