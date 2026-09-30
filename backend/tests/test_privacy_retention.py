"""개인정보처리방침과 코드가 맞는지: 탈퇴 시 지우는 것, 보상 기록 보관 기간."""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)


def test_탈퇴하면_행동_기록_커플_기록_유입_기록까지_지운다():
    from app.behavior import behavior_store
    from app.couples import couple_store
    from app.referrals import Acquisition, Reward, referral_store, utcnow

    body = client.post("/signup", json={"phone": "010-7070-1212"}).json()
    uid = body["user_id"]
    headers = {"X-User-Id": uid, "X-User-Token": body.get("token") or ""}
    behavior_store.bump(uid, ["cafe", "cafe"])
    rec = couple_store.get(f"{uid}:지은")
    rec.courses = 2
    couple_store.save(f"{uid}:지은", rec)
    referral_store.save(Acquisition(user_id=uid, source="threads"))
    assert referral_store.add_reward(Reward("k-" + uid, uid, "someone", None, utcnow()))

    assert client.delete(f"/users/{uid}", headers=headers).status_code == 200
    assert behavior_store.top_categories(uid) == []
    assert couple_store.get(f"{uid}:지은").courses == 0
    assert referral_store.get(uid) is None
    assert referral_store.rewarded("k-" + uid)  # 재보상 방지용 변환값은 남는다
    assert referral_store.last_reward_at(uid) is None


def test_보상_기록은_1년_지나면_지운다():
    from app.referrals import Reward, referral_store, utcnow

    old = utcnow() - timedelta(days=400)
    assert referral_store.add_reward(Reward("old-key", "a", "b", None, old))
    assert referral_store.prune_rewards() >= 1
    assert not referral_store.rewarded("old-key")
