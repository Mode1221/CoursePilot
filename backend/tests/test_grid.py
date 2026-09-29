"""상권 격자 분할: 카카오 질의 상한(45건)을 넘기기 위한 칸 나누기."""

from math import atan2, cos, radians, sin, sqrt

from app.batch.districts import DISTRICTS, District
from app.batch.grid import CELL_RADIUS_M, CELL_STEP_M, Cell, cells_for


def _distance_m(lat1, lng1, lat2, lng2):
    r = 6_371_000
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def test_작은_상권은_칸_하나():
    small = District("작은", 37.5, 127.0, 300, sigungu="성동구")
    assert cells_for(small) == [Cell(37.5, 127.0, 300, "c0")]


def test_큰_상권은_여러_칸으로_쪼개고_중심_칸이_있다():
    big = District("큰", 37.5445, 127.0557, 1000, sigungu="성동구")
    cells = cells_for(big)
    assert len(cells) > 9
    keys = {c.key for c in cells}
    assert "g+0+0" in keys and len(keys) == len(cells)  # 키는 유일(진행 상태 저장용)
    assert all(c.radius_m == CELL_RADIUS_M for c in cells)


def test_칸_중심은_상권_원_근처에만():
    big = District("큰", 37.5445, 127.0557, 1000, sigungu="성동구")
    for c in cells_for(big):
        assert _distance_m(big.lat, big.lng, c.lat, c.lng) <= big.radius_m + 1


def test_칸_간격은_빈틈_없이_덮는_조건을_만족():
    # 정사각 격자 간격 s, 원 반지름 r 이 r ≥ s/√2 여야 빈틈이 없다
    assert CELL_RADIUS_M >= CELL_STEP_M / 2**0.5


def test_실제_상권_24곳의_칸_수는_수백_개_안쪽():
    total = sum(len(cells_for(d)) for d in DISTRICTS)
    assert 24 <= total <= 600
