"""상권 좌표·반경 배치. 겹치면 같은 곳을 두 번 훑고, 어긋나면 엉뚱한 동네를 모은다."""
from math import asin, cos, radians, sin, sqrt

import pytest

from app.batch.districts import DISTRICTS

# 대표 역·랜드마크 좌표(2026-09 대조). 여기서 크게 벗어나면 좌표가 틀린 것이다.
LANDMARKS = {
    "성수": (37.5446, 127.0557), "연남": (37.5610, 126.9250), "홍대": (37.5570, 126.9245),
    "합정": (37.5495, 126.9137), "망원": (37.5560, 126.9105), "이태원": (37.5345, 126.9946),
    "한남": (37.5340, 127.0016), "을지로": (37.5662, 126.9917), "종로": (37.5704, 126.9920),
    "익선동": (37.5740, 126.9905), "서촌": (37.5790, 126.9700), "북촌": (37.5826, 126.9831),
    "강남역": (37.4979, 127.0276), "신사": (37.5163, 127.0203), "압구정": (37.5271, 127.0286),
    "청담": (37.5194, 127.0533), "삼성": (37.5089, 127.0631), "여의도": (37.5215, 126.9243),
    "영등포": (37.5158, 126.9074), "건대": (37.5403, 127.0700), "잠실": (37.5133, 127.1001),
    "신촌": (37.5551, 126.9368), "대학로": (37.5822, 127.0018), "판교": (37.3947, 127.1112),
}
MAX_GAP_M = 300
MAX_OVERLAP_M = 750  # 붙어 있는 동네끼리는 어쩔 수 없이 겹친다. 이 이상이면 사실상 같은 원.


def _distance_m(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lng2 - lng1)
    x = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6_371_000 * asin(sqrt(x))


def test_상권은_24곳이다():
    assert len(DISTRICTS) == 24
    assert len({d.name for d in DISTRICTS}) == 24


@pytest.mark.parametrize("district", DISTRICTS, ids=lambda d: d.name)
def test_좌표가_대표_지점에서_크게_벗어나지_않는다(district):
    lat, lng = LANDMARKS[district.name]
    gap = _distance_m(district.lat, district.lng, lat, lng)
    assert gap <= MAX_GAP_M, f"{district.name}: 기준점에서 {gap:.0f}m 벗어남"


def test_사실상_같은_원인_상권이_없다():
    heavy = []
    for i, a in enumerate(DISTRICTS):
        for b in DISTRICTS[i + 1 :]:
            overlap = a.radius_m + b.radius_m - _distance_m(a.lat, a.lng, b.lat, b.lng)
            if overlap > MAX_OVERLAP_M:
                heavy.append(f"{a.name}-{b.name}({overlap:.0f}m)")
    assert not heavy, f"겹침이 과한 쌍: {heavy}"


def test_반경이_도보권을_벗어나지_않는다():
    for district in DISTRICTS:
        assert 400 <= district.radius_m <= 1200, district.name


def test_배치_리포트가_돈다(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "districts_map.py"
    out = tmp_path / "map.html"
    proc = subprocess.run(
        [sys.executable, str(script), "--out", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    html = out.read_text()
    assert "<svg" in html and "겹치는 쌍" in html
    for district in DISTRICTS:
        assert district.name in html
