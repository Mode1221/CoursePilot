#!/usr/bin/env python
"""상권 좌표·반경을 지도로 찍어 본다(겹침·누락 확인용).

    python scripts/districts_map.py            # districts_map.html 생성
    python scripts/districts_map.py --open-path /tmp/map.html

지도 타일은 쓰지 않는다(키가 필요하고, 확인하려는 건 원의 배치뿐이다).
위경도를 그대로 평면에 투영해 원을 그리고, 겹치는 쌍을 함께 적는다.
"""
from __future__ import annotations

import argparse
import html
import sys
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.batch.districts import DISTRICTS, District  # noqa: E402

WIDTH, HEIGHT, MARGIN = 1000, 900, 60


def distance_m(a: District, b: District) -> float:
    r = 6_371_000
    p1, p2 = radians(a.lat), radians(b.lat)
    dp, dl = radians(b.lat - a.lat), radians(b.lng - a.lng)
    x = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(x))


def overlaps() -> list[tuple[District, District, float, float]]:
    """중심 거리가 반경 합보다 가까운 쌍(겹치는 만큼 같은 곳을 두 번 훑는다)."""
    found = []
    for i, a in enumerate(DISTRICTS):
        for b in DISTRICTS[i + 1 :]:
            gap = distance_m(a, b)
            overlap = a.radius_m + b.radius_m - gap
            if overlap > 0:
                found.append((a, b, gap, overlap))
    return sorted(found, key=lambda t: -t[3])


def _projection():
    """위경도 → 화면 좌표. 위도에 따라 경도 간격이 줄어드는 것만 보정한다."""
    lats = [d.lat for d in DISTRICTS]
    lngs = [d.lng for d in DISTRICTS]
    mid = radians(sum(lats) / len(lats))
    xs = [lng * cos(mid) for lng in lngs]
    x0, x1, y0, y1 = min(xs), max(xs), min(lats), max(lats)
    scale = min((WIDTH - 2 * MARGIN) / (x1 - x0), (HEIGHT - 2 * MARGIN) / (y1 - y0))

    def to_xy(lat: float, lng: float) -> tuple[float, float]:
        return (
            MARGIN + (lng * cos(mid) - x0) * scale,
            HEIGHT - MARGIN - (lat - y0) * scale,  # 위도는 위로 갈수록 커진다
        )

    # 반경(m)을 화면 픽셀로. 위도 1도 ≈ 111km
    meters_to_px = scale / 111_000
    return to_xy, meters_to_px


def render() -> str:
    to_xy, m2px = _projection()
    pairs = overlaps()
    tight = {d.name for a, b, _, ov in pairs if ov > 400 for d in (a, b)}

    circles, labels = [], []
    for d in DISTRICTS:
        x, y = to_xy(d.lat, d.lng)
        r = max(4.0, d.radius_m * m2px)
        color = "#d0453b" if d.name in tight else "#0f9d84"
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" '
            f'fill-opacity="0.12" stroke="{color}" stroke-width="1.5"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>'
        )
        labels.append(
            f'<text x="{x:.1f}" y="{y - r - 5:.1f}" text-anchor="middle" '
            f'font-size="12" fill="#16202a">{html.escape(d.name)}'
            f'<tspan font-size="10" fill="#5c6b7a"> {d.radius_m}m</tspan></text>'
        )

    rows = "".join(
        f"<tr><td>{html.escape(a.name)} ↔ {html.escape(b.name)}</td>"
        f"<td>{gap:,.0f}m</td><td>{ov:,.0f}m</td></tr>"
        for a, b, gap, ov in pairs
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>CoursePilot 상권 배치</title>
<style>
 body {{ font: 14px/1.6 system-ui, sans-serif; margin: 24px; color: #16202a; }}
 h1 {{ font-size: 20px; margin: 0 0 4px; }}
 p.note {{ color: #5c6b7a; margin: 0 0 16px; }}
 table {{ border-collapse: collapse; margin-top: 8px; }}
 th, td {{ border: 1px solid #e3e8ee; padding: 4px 10px; text-align: left; }}
 th {{ background: #f6f8fa; }}
 svg {{ border: 1px solid #e3e8ee; border-radius: 8px; background: #fbfcfd; }}
</style>
<h1>상권 {len(DISTRICTS)}곳 배치</h1>
<p class="note">지도 타일 없이 위경도를 평면에 투영했다(원의 배치만 본다).
빨간 원은 다른 상권과 400m 넘게 겹치는 곳.</p>
<svg width="{WIDTH}" height="{HEIGHT}">{"".join(circles)}{"".join(labels)}</svg>
<h2>겹치는 쌍 {len(pairs)}개</h2>
<table><tr><th>상권</th><th>중심 거리</th><th>겹침</th></tr>{rows}</table>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="상권 배치 확인용 HTML")
    ap.add_argument("--out", default="districts_map.html")
    args = ap.parse_args()

    Path(args.out).write_text(render(), encoding="utf-8")
    pairs = overlaps()
    print(f"상권 {len(DISTRICTS)}곳 → {args.out}")
    print(f"겹치는 쌍 {len(pairs)}개" + (f", 최대 겹침 {pairs[0][3]:,.0f}m" if pairs else ""))
    for a, b, gap, ov in pairs[:5]:
        print(f"  {a.name}-{b.name}: 거리 {gap:,.0f}m, 겹침 {ov:,.0f}m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
