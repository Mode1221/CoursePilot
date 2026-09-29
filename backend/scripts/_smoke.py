"""스모크 검증 공통 뼈대.

실키로 딱 한두 건만 부르고, "응답이 코드가 기대하는 모양인가"를 대조한다.
필드명이 바뀌거나 타입이 달라지면 어느 필드가 어떻게 다른지 찍는다.
키가 없으면 실패가 아니라 스킵이다(키는 하나씩 들어오므로).
"""
from __future__ import annotations

import sys
from typing import Any

RESET, RED, GREEN, YELLOW, DIM = "\033[0m", "\033[31m", "\033[32m", "\033[33m", "\033[2m"

SKIP_EXIT = 0  # 키 없음은 정상 종료 — CI·수동 실행 모두에서 실패로 보지 않는다
FAIL_EXIT = 1


def _type_name(value: Any) -> str:
    return type(value).__name__


def dig(obj: Any, path: str) -> tuple[bool, Any]:
    """'a.b[0].c' 경로를 따라간다. (찾았는지, 값)."""
    cur = obj
    for raw in path.split("."):
        key, _, idx = raw.partition("[")
        if key:
            if not isinstance(cur, dict) or key not in cur:
                return False, None
            cur = cur[key]
        if idx:
            i = int(idx.rstrip("]"))
            if not isinstance(cur, list) or len(cur) <= i:
                return False, None
            cur = cur[i]
    return True, cur


class Smoke:
    """한 벤더의 검증 결과를 모은다."""

    def __init__(self, vendor: str) -> None:
        self.vendor = vendor
        self.failures: list[str] = []
        self.checks = 0
        print(f"\n{'=' * 60}\n{vendor} 스모크\n{'=' * 60}")

    def note(self, message: str) -> None:
        print(f"{DIM}  · {message}{RESET}")

    def ok(self, message: str) -> None:
        self.checks += 1
        print(f"{GREEN}  ✓{RESET} {message}")

    def fail(self, message: str) -> None:
        self.checks += 1
        self.failures.append(message)
        print(f"{RED}  ✗{RESET} {message}")

    def field(
        self,
        payload: Any,
        path: str,
        expected: type | tuple[type, ...],
        *,
        required: bool = True,
    ) -> Any:
        """응답에서 코드가 읽는 필드 하나를 대조한다."""
        found, value = dig(payload, path)
        if not found:
            if required:
                near = ", ".join(sorted(payload)[:12]) if isinstance(payload, dict) else "?"
                self.fail(f"{path} 없음 — 응답에 있는 키: {near}")
            else:
                self.note(f"{path} 없음(선택 필드라 통과)")
            return None
        if value is None:
            if required:
                self.fail(f"{path} 이 null")
            else:
                self.note(f"{path} 은 null(선택 필드라 통과)")
            return None
        if not isinstance(value, expected):
            want = getattr(expected, "__name__", str(expected))
            self.fail(f"{path} 타입이 {_type_name(value)} (코드가 기대: {want}) 값={value!r}")
            return value
        shown = str(value)
        self.ok(f"{path} = {shown[:60]}{'…' if len(shown) > 60 else ''} ({_type_name(value)})")
        return value

    def equals(self, label: str, actual: Any, expected: Any) -> None:
        if actual == expected:
            self.ok(f"{label} = {actual!r}")
        else:
            self.fail(f"{label} 이 {actual!r} (기대: {expected!r})")

    def truthy(self, label: str, value: Any) -> None:
        if value:
            self.ok(f"{label}: {str(value)[:60]}")
        else:
            self.fail(f"{label} 이 비었음 ({value!r})")

    def done(self) -> int:
        if self.failures:
            print(f"\n{RED}FAIL{RESET} {self.vendor} — {len(self.failures)}/{self.checks} 불일치")
            for f in self.failures:
                print(f"    - {f}")
            return FAIL_EXIT
        print(f"\n{GREEN}PASS{RESET} {self.vendor} — {self.checks}개 항목 일치")
        return 0


def skip(vendor: str, reason: str) -> int:
    print(f"\n{'=' * 60}\n{vendor} 스모크\n{'=' * 60}")
    print(f"{YELLOW}SKIP{RESET} {vendor} — {reason}")
    return SKIP_EXIT


def run(main) -> None:
    """스크립트 진입점. 예외도 FAIL 로 보고한다(스택 대신 한 줄)."""
    import asyncio

    try:
        code = asyncio.run(main())
    except Exception as exc:  # noqa: BLE001 - 스모크는 어떤 실패든 한 줄로 보고한다
        print(f"{RED}FAIL{RESET} 호출 자체가 실패: {type(exc).__name__}: {exc}")
        code = FAIL_EXIT
    sys.exit(code)
