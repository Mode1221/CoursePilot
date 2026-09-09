"""질문에는 코스를 갈아엎지 않고 답한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import _is_question, api

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-3232-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return uid, cid


def test_질문_판정():
    for text in ("여기 주차 되나요?", "총 얼마나 걸려?", "2번째 어디야?", "괜찮을까요"):
        assert _is_question(text), text
    for text in ("성수동 저녁 데이트", "2번째 빼줘"):
        assert not _is_question(text), text


def test_질문에는_코스를_바꾸지_않고_답한다():
    uid, cid = _course()
    before = client.get(f"/courses/{cid}").json()["items"]
    credits = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()[
        "questions_left"
    ]

    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "여기 주차 되나요?"},
    )

    after = client.get(f"/courses/{cid}").json()["items"]
    text = client.get(f"/courses/{cid}/messages").json()[-1]["text"]
    assert [i["place"]["id"] for i in after] == [i["place"]["id"] for i in before]
    # 주차를 물었으면 주차로 답한다(코스 요약을 되풀이하지 않는다)
    assert "주차" in text
    assert (
        client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()[
            "questions_left"
        ]
        == credits
    )


def test_물음표가_붙은_편집_요청은_편집으로_처리한다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "2번째 카페로 바꿔줄래?"},
    )
    assert "바꿨어요" in client.get(f"/courses/{cid}/messages").json()[-1]["text"]
