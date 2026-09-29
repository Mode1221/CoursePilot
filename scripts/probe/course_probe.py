#!/usr/bin/env python3
"""운영 코스 품질 즉석 점검 — 예시 문장으로 실제 코스를 만들어 표로 정리한다(표준 라이브러리만).

  QA_TOKEN=... python3 scripts/probe/course_probe.py [prompts.json] > report.md

QA 전용 계정(/admin/qa-session)으로 만들고 끝나면 지운다. QA 요청이라 학습 신호에 섞이지 않는다.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("QA_API_URL") or "https://api.coursepilot-kr.duckdns.org"
TOKEN = os.environ["QA_TOKEN"]

# (문장, 기대 구(區) 후보, 핵심 키워드)
DEFAULT = [
    ("토요일 오후 2시 성수동에서 브런치 먹고 카페랑 소품샵 구경하고 싶어", ["성동구"], ["브런치", "카페", "소품"]),
    ("일요일 저녁 6시 연남동에서 파스타 먹고 와인바 가자", ["마포구"], ["파스타", "와인"]),
    ("비 오는 토요일 오후 1시 잠실에서 실내 데이트", ["송파구"], []),
    ("금요일 저녁 7시 을지로 노포 고기집 가고 2차는 술집", ["중구"], ["고기", "술"]),
    ("토요일 오전 11시 북촌 한옥마을 산책하고 한식으로 점심", ["종로구"], ["한식"]),
    ("평일 저녁 7시 강남역 근처 둘이 3만원 이하로 저렴하게", ["강남구", "서초구"], []),
    ("일요일 오후 3시 망원동 한강 산책하고 디저트 먹기", ["마포구"], ["디저트"]),
    ("토요일 오후 4시 이태원에서 전시 보고 저녁은 멕시칸", ["용산구"], ["전시", "멕시"]),
    ("첫 데이트라 토요일 오후 5시 삼청동 조용한 곳 위주로", ["종로구"], []),
    ("금요일 밤 9시 홍대에서 늦게까지 여는 곳 위주로 심야 데이트", ["마포구"], []),
]


def call(method: str, path: str, body: dict | None = None, headers: dict | None = None, timeout: int = 120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-QA-Token", TOKEN)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"")[:300].decode("utf-8", "replace")


def main() -> int:
    prompts = DEFAULT
    if len(sys.argv) > 1:
        prompts = [tuple(p) for p in json.load(open(sys.argv[1], encoding="utf-8"))]
    status, me = call("POST", "/admin/qa-session")
    if status != 200:
        print(f"QA 세션 실패: {status} {me}")
        return 1
    auth = {"X-User-Id": me["user_id"], "X-User-Token": me["token"]}

    out: list[str] = ["# 코스 품질 즉석 점검", "", f"대상: `{API}` · {time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 9 * 3600))} KST", ""]
    summary: list[str] = ["| # | 요청 | 장소 수 | 지역 | 키워드 | 영업시간 충돌 | 시간 확인 필요 | 최장 이동 | 완화 | 소요 |", "|---|---|---|---|---|---|---|---|---|---|"]
    details: list[str] = []
    ok = 0
    for i, (text, gus, kws) in enumerate(prompts, 1):
        status, course = call("POST", "/courses", {}, auth)
        if status != 200:
            summary.append(f"| {i} | {text} | 생성 실패 {status} | | | | | | | |")
            continue
        cid = course["id"]
        t0 = time.time()
        status, res = call("POST", f"/courses/{cid}/generate", {"text": text}, auth, timeout=180)
        took = time.time() - t0
        try:
            if status != 200:
                summary.append(f"| {i} | {text} | 오류 {status} | | | | | | | {took:.0f}s |")
                details.append(f"### {i}. {text}\n\n오류 {status}: `{res}`\n")
                continue
            items = res["course"]["items"]
            places = [it["place"] for it in items]
            in_area = sum(1 for p in places if any(g in (p.get("address") or "") for g in gus))
            hay = " ".join(f"{p.get('name','')} {p.get('category','')}" for p in places)
            kw_hit = [k for k in kws if k in hay]
            conflicts = sum(1 for it in items if it.get("hours_conflict"))
            unverified = sum(1 for p in places if p.get("hours_unverified") or not p.get("open_time"))
            legs = [it["travel_to_next"]["duration_min"] for it in items if it.get("travel_to_next")]
            longest = max(legs) if legs else 0
            relaxed = "완화" if res.get("relaxed") else ("확인 필요" if res.get("needs_confirmation") else "-")
            good = len(places) >= 3 and in_area >= len(places) - 1 and conflicts == 0 and longest <= 30
            ok += good
            summary.append(
                f"| {i} | {text} | {len(places)} | {in_area}/{len(places)} | {', '.join(kw_hit) or '-'}"
                f"{'' if not kws else f' ({len(kw_hit)}/{len(kws)})'} | {conflicts} | {unverified} | {longest}분 | {relaxed} | {took:.0f}s |"
            )
            rows = [f"### {i}. {text}", "", "| 시각 | 장소 | 분류 | 주소 | 영업 | 평점 | 다음 이동 |", "|---|---|---|---|---|---|---|"]
            for it in items:
                p = it["place"]
                arrive = (it.get("arrive") or "")[:5]
                hours = f"{(p.get('open_time') or '')[:5]}~{(p.get('close_time') or '')[:5]}" if p.get("open_time") else "확인 필요"
                if it.get("hours_conflict"):
                    hours += " ⚠충돌"
                rating = f"{p['rating']:.1f}({p.get('rating_count') or '?'})" if p.get("rating") else "-"
                nxt = it.get("travel_to_next")
                move = f"{nxt['mode']} {nxt['duration_min']}분" if nxt else ""
                cat = (p.get("category") or "").split(">")[-1].strip()
                addr = " ".join((p.get("address") or "").split()[:3])
                rows.append(f"| {arrive} | {p.get('name')} | {cat} | {addr} | {hours} | {rating} | {move} |")
            dbg = res.get("debug") or []
            if dbg:
                rows.append("")
                rows.append("단계별(ms): " + " · ".join(f"{n} {v}" for n, v in dbg))
            details.append("\n".join(rows) + "\n")
        finally:
            call("DELETE", f"/courses/{cid}", None, auth)
        time.sleep(2)
    out.append(f"**자동 판정 통과 {ok}/{len(prompts)}** (장소 3곳 이상 · 지역 이탈 최대 1곳 · 영업시간 충돌 0 · 최장 이동 30분 이하)")
    out += ["", *summary, "", "## 코스별 상세", "", *details]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
