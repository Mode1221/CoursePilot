"""운영 지표 — Atelier 본부 "운영 지표"(방문·기능별 사용·유입 출처)로 보내는 날짜별 집계.

형식은 Atelier 공통 형식(ops-stats): {at, series, days[{date, <키>…}], sources, totals}.
개인정보 없이 개수만. 운영 자동 QA 는 체험·퍼널에 처음부터 기록되지 않으므로 숫자에 섞이지 않는다.
날짜는 한국 날짜: 체험·가입 시각은 UTC 로 저장돼 +9시간, 퍼널 시각은 서버 지역 시각 그대로(funnel.py 와 같은 기준).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

# 화면에 보일 이름. 첫 키가 주 지표.
SERIES = {
    "visitors": "새 방문(기기)",
    "guests": "새 체험 사용자",
    "signups": "가입",
    "started": "같이 정하기 링크 만들기",
    "link_opened": "상대가 링크 엶",
    "built": "코스 만들기",
    "confirmed": "둘 다 확정",
    "completed": "다녀왔어요",
}
FUNNEL_KEYS = ("started", "link_opened", "built", "confirmed", "completed")
KST = timedelta(hours=9)


def _kst_date(dt: datetime, utc: bool) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
        utc = True
    return (dt + KST if utc else dt).date().isoformat()


def daily_stats(days: int = 14, now: datetime | None = None) -> dict:
    from app.funnel import funnel_store
    from app.referrals import SOURCE_DIRECT, referral_store, utcnow

    now_utc = now or utcnow()
    if now_utc.tzinfo is not None:
        now_utc = now_utc.astimezone(UTC).replace(tzinfo=None)
    today = (now_utc + KST).date()
    dates = [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    rows = {d: {"date": d, **{k: 0 for k in SERIES}} for d in dates}
    since = now_utc - timedelta(days=days + 1)
    sources: dict[str, int] = {}
    for a in referral_store.acquisitions_since(since):
        if a.guest_at:
            d = _kst_date(a.guest_at, utc=True)
            if d in rows:
                rows[d]["guests"] += 1
                src = a.source or SOURCE_DIRECT
                sources[src] = sources.get(src, 0) + 1
        if a.member_at:
            d = _kst_date(a.member_at, utc=True)
            if d in rows:
                rows[d]["signups"] += 1
    from app.visits import visit_store

    visit_sources: dict[str, int] = {}
    for day, src, n in visit_store.since(dates[0]):
        if day in rows:
            rows[day]["visitors"] += n
            visit_sources[src] = visit_sources.get(src, 0) + n
    for e in funnel_store.events(since=datetime.now() - timedelta(days=days + 1)):
        if e.name in FUNNEL_KEYS:
            d = _kst_date(e.at, utc=False)
            if d in rows:
                rows[d][e.name] += 1
    out_days = [rows[d] for d in dates]
    last7 = out_days[-7:]
    return {
        "at": now_utc.replace(microsecond=0).isoformat() + "Z",
        "series": SERIES,
        "days": out_days,
        "sources": dict(sorted(sources.items(), key=lambda kv: -kv[1])),
        # 출처별 방문 → 체험 시작 (홍보 글이 사람을 데려왔는지, 들어와서 시작했는지)
        "visit_sources": dict(sorted(visit_sources.items(), key=lambda kv: -kv[1])),
        "totals": {
            "최근 7일 새 방문": sum(r["visitors"] for r in last7),
            "최근 7일 새 체험": sum(r["guests"] for r in last7),
            "최근 7일 가입": sum(r["signups"] for r in last7),
            "최근 7일 코스 만들기": sum(r["built"] for r in last7),
            "최근 7일 둘 다 확정": sum(r["confirmed"] for r in last7),
        },
    }
