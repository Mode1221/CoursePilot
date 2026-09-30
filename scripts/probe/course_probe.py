#!/usr/bin/env python3
"""운영 코스 품질 점검 — 예시 문장으로 실제 코스를 두 번씩 만들어 정확도·신뢰도·일관성을 잰다(표준 라이브러리만).

  QA_TOKEN=... python3 scripts/probe/course_probe.py > report.md

QA 전용 계정(/admin/qa-session)으로 만들고 끝나면 지운다. QA 요청이라 학습 신호에 섞이지 않는다.

점수(코스마다 0~100, 평균):
- 정확도 = 요청을 지켰나 — 말한 동네 안(구 기준) 비율 · 말한 것(음식·장소 종류)이 들어간 비율 · 빼 달라는 것 안 들어감 · 개수 충족
- 신뢰도 = 믿고 가도 되나 — 영업시간을 아는 곳 비율 · 평점 표본 30개 이상 비율 · 영업시간 충돌 없음 · 구간 이동 25분 이하 비율
- 일관성 = 같은 문장을 두 번 만들었을 때 겹치는 장소 비율(너무 낮으면 들쭉날쭉, 100이면 늘 같은 코스)
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("QA_API_URL") or "https://api.coursepilot-kr.duckdns.org"
TOKEN = os.environ["QA_TOKEN"]
BAR = ["술", "호프", "주점", "와인", "칵테일", "이자카야", "포차", "펍", " 바", "바 "]

# 문장 · 기대 구 · 들어가야 할 것(묶음마다 하나라도) · 들어가면 안 되는 것 · 최소 장소 수
PROMPTS: list[dict] = [
    {"text": "토요일 오후 2시 성수동에서 브런치 먹고 카페랑 소품샵 구경하고 싶어", "gu": ["성동구"],
     "want": [["브런치"], ["카페", "커피", "베이커리", "제과", "디저트"], ["소품", "잡화", "편집", "액세서리", "생활용품", "문구"]], "min": 3},
    {"text": "일요일 저녁 6시 연남동에서 파스타 먹고 와인바 가자", "gu": ["마포구"],
     "want": [["파스타", "이탈리", "양식"], ["와인"]], "min": 2},
    {"text": "비 오는 토요일 오후 1시 잠실에서 실내 데이트", "gu": ["송파구"], "min": 3},
    {"text": "금요일 저녁 7시 을지로 노포 고기집 가고 2차는 술집", "gu": ["중구"],
     "want": [["고기", "갈비", "구이", "육류", "삼겹"], BAR], "min": 2},
    {"text": "토요일 오전 11시 북촌 한옥마을 산책하고 한식으로 점심", "gu": ["종로구"],
     "want": [["한옥", "북촌"], ["한식", "칼국수", "국수", "백반", "한정식"]], "min": 3},
    {"text": "평일 저녁 7시 강남역 근처 둘이 3만원 이하로 저렴하게", "gu": ["강남구", "서초구"], "min": 2},
    {"text": "일요일 오후 3시 망원동 한강 산책하고 디저트 먹기", "gu": ["마포구"],
     "want": [["한강", "공원"], ["디저트", "케이크", "티라미수", "베이커리", "제과"]], "min": 3},
    {"text": "토요일 오후 4시 이태원에서 전시 보고 저녁은 멕시칸", "gu": ["용산구"],
     "want": [["전시", "갤러리", "미술"], ["멕시"]], "min": 3},
    {"text": "첫 데이트라 토요일 오후 5시 삼청동 조용한 곳 위주로", "gu": ["종로구"], "min": 3},
    {"text": "금요일 밤 9시 홍대에서 늦게까지 여는 곳 위주로 심야 데이트", "gu": ["마포구"], "want": [BAR], "min": 2},
    # 규칙 해석이 약한 문장 — AI 차이가 드러나는 쪽
    {"text": "비 오는 일요일 오후 2시 홍대에서 실내로만, 매운 건 못 먹어", "gu": ["마포구"],
     "avoid": ["마라", "매운", "떡볶이", "짬뽕", "불닭"], "min": 3},
    {"text": "강남역에서 저녁 7시부터 3시간, 1인 4만원 안쪽으로 조용한 데", "gu": ["강남구", "서초구"], "min": 2},
    {"text": "부모님 모시고 토요일 점심 북촌, 많이 안 걷게", "gu": ["종로구"],
     "avoid": ["술집", "호프", "주점", "포차", "와인바", "칵테일"], "min": 2},
    {"text": "성수에서 카페 두 군데 가고 저녁은 고기, 술집은 빼고", "gu": ["성동구"],
     "want": [["카페", "커피", "베이커리", "디저트"], ["고기", "갈비", "구이", "육류", "삼겹"]],
     "avoid": ["술집", "호프", "요리주점", "포차", "이자카야", "와인바", "칵테일"], "min": 3},
    {"text": "금요일 밤 10시 이태원 루프탑 바 가고 2차는 칵테일", "gu": ["용산구"],
     "want": [["루프탑"], ["칵테일", "바"]], "min": 2},
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


def make(text: str, auth: dict) -> tuple[int, dict | str, float]:
    status, course = call("POST", "/courses", {}, auth)
    if status != 200:
        return status, str(course), 0.0
    cid = course["id"]
    t0 = time.time()
    try:
        status, res = call("POST", f"/courses/{cid}/generate", {"text": text}, auth, timeout=180)
        return status, res, time.time() - t0
    finally:
        call("DELETE", f"/courses/{cid}", None, auth)


def hay(p: dict) -> str:
    return f" {p.get('name', '')} {p.get('category', '')} "


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def score(spec: dict, items: list[dict]) -> dict:
    places = [it["place"] for it in items]
    n = len(places)
    text = " ".join(hay(p) for p in places)
    acc: dict[str, float] = {}
    acc["동네"] = sum(1 for p in places if any(g in (p.get("address") or "") for g in spec["gu"])) / n
    if spec.get("want"):
        acc["요청"] = sum(1 for grp in spec["want"] if any(w in text for w in grp)) / len(spec["want"])
    if spec.get("avoid"):
        acc["제외"] = 0.0 if any(w in text for w in spec["avoid"]) else 1.0
    acc["개수"] = 1.0 if n >= spec.get("min", 3) else n / spec.get("min", 3)
    legs = [it["travel_to_next"]["duration_min"] for it in items if it.get("travel_to_next")]
    rel = {
        "영업시간": sum(1 for p in places if p.get("open_time") and not p.get("hours_unverified")) / n,
        "평점": sum(1 for p in places if p.get("rating") and (p.get("rating_count") or 0) >= 30) / n,
        "충돌없음": 0.0 if any(it.get("hours_conflict") for it in items) else 1.0,
        "이동": (sum(1 for m in legs if m <= 25) / len(legs)) if legs else 1.0,
    }
    return {"acc": mean(list(acc.values())) * 100, "rel": mean(list(rel.values())) * 100, "acc_parts": acc, "rel_parts": rel}


def pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.0f}"


def main() -> int:
    status, me = call("POST", "/admin/qa-session")
    if status != 200:
        print(f"QA 세션 실패: {status} {me}")
        return 1
    auth = {"X-User-Id": me["user_id"], "X-User-Token": me["token"]}
    now = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 9 * 3600))

    only = {int(x) for x in os.environ.get("PROBE_ONLY", "").split(",") if x.strip().isdigit()}
    rows, details = [], []
    accs, rels, cons, secs, ai_ms = [], [], [], [], []
    ok_runs = total_runs = 0
    for i, spec in enumerate(PROMPTS, 1):
        if only and i not in only:
            continue
        runs = []
        for _ in range(2):
            total_runs += 1
            status, res, sec = make(spec["text"], auth)
            if status == 200 and isinstance(res, dict) and res["course"]["items"]:
                ok_runs += 1
                runs.append((res, sec))
                secs.append(sec)
                dbg = dict(res.get("debug") or [])
                if "decompose" in dbg:
                    ai_ms.append(dbg["decompose"])
            time.sleep(1)
        if not runs:
            rows.append(f"| {i} | {spec['text']} | 실패 | | | | | |")
            continue
        s = score(spec, runs[0][0]["course"]["items"])
        accs.append(s["acc"])
        rels.append(s["rel"])
        con = None
        if len(runs) == 2:
            a = {it["place"]["id"] for it in runs[0][0]["course"]["items"]}
            b = {it["place"]["id"] for it in runs[1][0]["course"]["items"]}
            con = len(a & b) / len(a | b) * 100
            cons.append(con)
        parts = " ".join(f"{k}{v * 100:.0f}" for k, v in s["acc_parts"].items())
        rparts = " ".join(f"{k}{v * 100:.0f}" for k, v in s["rel_parts"].items())
        items = runs[0][0]["course"]["items"]
        rows.append(
            f"| {i} | {spec['text']} | {len(items)}곳 | **{pct(s['acc'])}** ({parts}) | **{pct(s['rel'])}** ({rparts}) "
            f"| {pct(con)} | {runs[0][1]:.1f}s | {dict(runs[0][0].get('debug') or []).get('decompose', '-')}ms |"
        )
        lines = [f"### {i}. {spec['text']}", "", "| 시각 | 장소 | 분류 | 주소 | 영업 | 평점 | 다음 이동 |", "|---|---|---|---|---|---|---|"]
        for it in items:
            p = it["place"]
            hours = f"{(p.get('open_time') or '')[:5]}~{(p.get('close_time') or '')[:5]}" if p.get("open_time") else "확인 필요"
            rating = f"{p['rating']:.1f}({p.get('rating_count') or '?'})" if p.get("rating") else "-"
            nxt = it.get("travel_to_next")
            move = f"{nxt['mode']} {nxt['duration_min']}분" if nxt else ""
            cat = (p.get("category") or "").split(">")[-1].strip()
            addr = " ".join((p.get("address") or "").split()[:3])
            lines.append(f"| {(it.get('arrive') or '')[:5]} | {p.get('name')} | {cat} | {addr} | {hours} | {rating} | {move} |")
        dc = runs[0][0].get("debug_constraints")
        if dc:
            lines += ["", "해석된 조건: " + ", ".join(f"{k}={v}" for k, v in dc.items() if v not in (None, [], ""))]
        details.append("\n".join(lines) + "\n")

    med = statistics.median(secs) if secs else 0
    out = [
        "# 코스 품질 점검 (정확도·신뢰도·일관성)", "",
        f"대상: `{API}` · {now} KST · 문장 {len(PROMPTS)}개 × 2회", "",
        "| 지표 | 값 |", "|---|---|",
        f"| **정확도** (요청을 지켰나) | **{pct(mean(accs))}점** |",
        f"| **신뢰도** (믿고 가도 되나) | **{pct(mean(rels))}점** |",
        f"| 일관성 (같은 문장 두 번 → 겹친 장소) | {pct(mean(cons))}% |",
        f"| 성공 | {ok_runs}/{total_runs} |",
        f"| 코스 생성 시간 (중앙값 / 최대) | {med:.1f}초 / {max(secs) if secs else 0:.1f}초 |",
        f"| 문장 해석 AI 사용 | {sum(1 for m in ai_ms if m > 50)}/{len(ai_ms)} (평균 {pct(mean(ai_ms))}ms) |",
        "",
        "정확도 = 동네 안 비율·말한 것 반영·빼 달라는 것 없음·개수 / 신뢰도 = 영업시간 아는 곳·평점 표본 30+·영업시간 충돌 없음·이동 25분 이하",
        "",
        "| # | 요청 | 장소 | 정확도 (세부) | 신뢰도 (세부) | 일관성 | 소요 | 해석 |",
        "|---|---|---|---|---|---|---|---|",
        *rows, "", "## 코스별 상세 (1회차)", "", *details,
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
