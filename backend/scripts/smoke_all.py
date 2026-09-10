#!/usr/bin/env python
"""모든 벤더 스모크를 한 번에.

    python scripts/smoke_all.py            # 전부
    python scripts/smoke_all.py kakao naver

각 스크립트를 별도 프로세스로 돌리고 PASS/FAIL/SKIP 을 모아 요약한다.
키가 없는 벤더는 SKIP 이며 종료 코드에 영향을 주지 않는다.
하나라도 FAIL 이면 1 로 끝난다(키를 새로 넣은 뒤 확인용).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDORS = ("kakao", "naver", "tourapi", "kopis", "localdata", "google")
RESET, RED, GREEN, YELLOW = "\033[0m", "\033[31m", "\033[32m", "\033[33m"


def main() -> int:
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")] or list(VENDORS)
    unknown = [w for w in wanted if w not in VENDORS]
    if unknown:
        print(f"모르는 벤더: {unknown} (가능: {list(VENDORS)})")
        return 2

    results: dict[str, str] = {}
    for vendor in wanted:
        script = HERE / f"smoke_{vendor}.py"
        proc = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True
        )
        sys.stdout.write(proc.stdout)
        if proc.stderr.strip():
            sys.stderr.write(proc.stderr)
        out = proc.stdout
        if proc.returncode != 0:
            results[vendor] = "FAIL"
        elif "SKIP" in out:
            results[vendor] = "SKIP"
        else:
            results[vendor] = "PASS"

    print(f"\n{'=' * 60}\n요약\n{'=' * 60}")
    color = {"PASS": GREEN, "FAIL": RED, "SKIP": YELLOW}
    for vendor in wanted:
        state = results[vendor]
        print(f"  {color[state]}{state:<4}{RESET}  {vendor}")
    failed = [v for v, r in results.items() if r == "FAIL"]
    skipped = [v for v, r in results.items() if r == "SKIP"]
    if skipped:
        print(f"\n키 없음(스킵): {', '.join(skipped)} — 키가 들어오면 다시 돌릴 것")
    if failed:
        print(f"\n{RED}실패: {', '.join(failed)}{RESET}")
        return 1
    print(f"\n{GREEN}실패 없음{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
