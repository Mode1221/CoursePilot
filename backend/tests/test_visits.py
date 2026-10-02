"""방문 세기(POST /visit) — 홍보 글을 보고 들어왔다가 그냥 나간 사람도 날짜·출처별 개수로 보인다."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import api
from app.ops_stats import daily_stats
from app.referrals import Acquisition, referral_store
from app.visits import kst_day, visit_store

client = TestClient(api)


def test_첫_방문을_출처별로_세고_같은_IP_는_하루_한_번만():
    now = datetime(2026, 10, 2, 3, 0, tzinfo=UTC)
    assert visit_store.record("threads", "1.1.1.1", now) is True
    assert visit_store.record("threads", "1.1.1.1", now) is False  # 새로고침·다시 보내기
    assert visit_store.record("threads", "2.2.2.2", now) is True
    assert visit_store.record("Threads!!", "3.3.3.3", now) is True  # 정리 규칙은 유입 출처와 같다
    assert visit_store.record(None, "1.1.1.1", now) is True  # 출처 없음 = direct
    rows = {(d, s): n for d, s, n in visit_store.since("2026-10-01")}
    assert rows == {("2026-10-02", "threads"): 3, ("2026-10-02", "direct"): 1}


def test_한국_날짜로_센다():
    assert kst_day(datetime(2026, 10, 1, 16, 0, tzinfo=UTC)) == "2026-10-02"  # 한국 새벽 1시


def test_운영_지표에_방문과_방문_출처가_나온다():
    now = datetime(2026, 10, 2, 3, 0)
    for ip in ("1", "2", "3"):
        visit_store.record("threads", ip, datetime(2026, 10, 2, 3, 0, tzinfo=UTC))
    referral_store.save(Acquisition(user_id="g1", source="threads", guest_at=now))
    s = daily_stats(days=7, now=now)
    today = s["days"][-1]
    assert today["visitors"] == 3 and today["guests"] == 1
    assert s["visit_sources"] == {"threads": 3}
    assert s["totals"]["최근 7일 새 방문"] == 3


def test_엔드포인트는_204_이고_개수만_남는다():
    r = client.post("/visit", json={"source": "threads"})
    assert r.status_code == 204 and r.content == b""
    assert client.post("/visit", json={}).status_code == 204
    assert client.post("/visit", json={"source": "x" * 100}).status_code == 422
    total = sum(n for _, _, n in visit_store.since("2000-01-01"))
    assert total == 2  # 같은 테스트 IP 라도 출처가 다르면 따로(threads, direct)


def test_봇은_세지_않는다():
    client.post("/visit", json={"source": "threads"}, headers={"User-Agent": "facebookexternalhit/1.1"})
    client.post("/visit", json={"source": "threads"}, headers={"User-Agent": "Mozilla/5.0 HeadlessChrome/120"})
    assert visit_store.since("2000-01-01") == []


def test_QA_요청은_세지_않는다(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "qa_token", "qa-secret")
    r = client.post("/visit", json={"source": "threads"}, headers={"X-QA-Token": "qa-secret"})
    assert r.status_code == 204
    assert visit_store.since("2000-01-01") == []
