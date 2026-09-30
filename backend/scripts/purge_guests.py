#!/usr/bin/env python
"""가입하지 않은 체험 계정 정리 + 오래된 사용 한도 카운터 정리.

    python scripts/purge_guests.py            # 30일 지난 체험 계정
    python scripts/purge_guests.py --days 7

체험은 로그인 없이 한 번 써 보는 기능이다. 가입하지 않은 사람의 코스·대화를 계속
들고 있을 이유가 없다(개인정보처리방침: 체험 기록은 30일 뒤 삭제). 크론: 매일 05:45.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.batch.db_setup import connect_db  # noqa: E402
from app.identity import purge_guests  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="체험 계정·사용 카운터 정리")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    connect_db()
    report = purge_guests(args.days)
    from app.referrals import referral_store

    rewards = referral_store.prune_rewards()  # 1년 지난 초대 보상 기록(처리방침 3항)
    print(
        f"체험 계정 {report['guests']}개 · 코스 {report['courses']}개 삭제, "
        f"지난 카운터 {report['counters']}행 정리, 1년 지난 보상 기록 {rewards}행 삭제"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
