"""모델·effort 별 실측 비교 — 우리 실제 조건 분해 요청(도구 스키마 포함)으로 토큰·지연·비용·정확도를 잰다.

  docker compose -f docker-compose.prod.yml exec -T backend python scripts/llm_bench.py
  (옵션) --n 3  문장 수 / --only haiku,sonnet  모델 거르기

서비스 한도(usage.py)를 거치지 않고 키로 직접 부른다. 기본 구성 전체 1회 ≈ US$1 안팎(Fable high 가 대부분).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.pipeline.llm import _ANTHROPIC_TOOL, _SYSTEM, _TOOL_NAME  # noqa: E402

# (모델, effort) — effort 미지원 모델은 None
CONFIGS: list[tuple[str, str | None]] = [
    ("claude-haiku-4-5", None),
    ("claude-sonnet-5-5", "low"),
    ("claude-sonnet-5-5", "medium"),
    ("claude-sonnet-5-5", "high"),
    ("claude-opus-5-5", "low"),
    ("claude-opus-5-5", "medium"),
    ("claude-opus-5-5", "high"),
    ("claude-fable-5-1", "low"),
    ("claude-fable-5-1", "medium"),
    ("claude-fable-5-1", "high"),
]
# 100만 토큰당 (입력, 출력) US$ — platform.claude.com/docs/en/about-claude/pricing (2026-09-30)
PRICE = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-fable-5-1": (10.0, 50.0),
}
KRW = 1400
SENTENCES = [
    "토요일 오후 2시 성수동에서 브런치 먹고 카페랑 소품샵 구경하고 싶어",
    "일요일 저녁 6시 연남동에서 파스타 먹고 와인바 가자",
    "비 오는 토요일 오후 1시 잠실에서 실내 데이트, 둘이서 5만원 안쪽",
    "금요일 저녁 7시 을지로 노포 고기집 가고 2차는 술집, 술은 너무 시끄러운 데 빼고",
    "첫 데이트라 토요일 오후 5시 삼청동 조용한 곳 위주로 3시간 정도",
]


async def one(client, model: str, effort: str | None, text: str) -> dict:
    kw: dict = {
        "model": model,
        "system": _SYSTEM + " 반드시 set_constraints 도구 한 번으로 답한다.",
        "tools": [_ANTHROPIC_TOOL],
        "messages": [{"role": "user", "content": text}],
    }
    if effort is None:
        kw["max_tokens"] = 512
        kw["tool_choice"] = {"type": "tool", "name": _TOOL_NAME}  # 지금 운영과 같은 방식
    else:
        kw["max_tokens"] = 16_000  # 생각 토큰도 여기에 들어간다
        kw["tool_choice"] = {"type": "auto"}  # 5.x 는 도구 강제 호출을 받지 않는다
        kw["extra_body"] = {"output_config": {"effort": effort}}
    t0 = time.perf_counter()
    try:
        resp = await client.messages.create(**kw)
    except Exception as exc:  # noqa: BLE001 - 벤치: 실패도 결과로 남긴다
        return {"ok": False, "err": f"{type(exc).__name__}: {str(exc)[:80]}", "sec": time.perf_counter() - t0}
    sec = time.perf_counter() - t0
    args = next((dict(b.input) for b in resp.content if b.type == "tool_use" and b.name == _TOOL_NAME), None)
    return {
        "ok": args is not None,
        "in": resp.usage.input_tokens,
        "out": resp.usage.output_tokens,
        "sec": sec,
        "args": args or {},
    }


def cost(model: str, tin: float, tout: float) -> float:
    pin, pout = PRICE[model]
    return tin / 1e6 * pin + tout / 1e6 * pout


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=len(SENTENCES))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    from anthropic import AsyncAnthropic

    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY 가 없습니다.")
        return
    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=120)
    sentences = SENTENCES[: a.n]
    only = [s.strip() for s in a.only.split(",") if s.strip()]
    configs = [c for c in CONFIGS if not only or any(o in c[0] for o in only)]

    rows, samples = [], []
    for model, effort in configs:
        # 문장은 차례로(동시에 쏘면 지연이 섞인다)
        res = [await one(client, model, effort, s) for s in sentences]
        ok = [r for r in res if r["ok"]]
        name = model.replace("claude-", "") + (f" · {effort}" if effort else "")
        if not ok:
            err = next((r.get("err") for r in res if r.get("err")), "도구 호출 없음")
            rows.append(f"| {name} | - | - | - | 0/{len(res)} | - | - | {err} |")
            continue
        tin = sum(r["in"] for r in ok) / len(ok)
        tout = sum(r["out"] for r in ok) / len(ok)
        sec = sum(r["sec"] for r in ok) / len(ok)
        worst = max(r["sec"] for r in ok)
        c = cost(model, tin, tout)
        rows.append(
            f"| {name} | {tin:.0f} | {tout:.0f} | {sec:.1f}s (최대 {worst:.1f}s) | {len(ok)}/{len(res)} "
            f"| {c * KRW:.1f}원 | {c * 1000:.2f}$ | |"
        )
        first = ok[0]["args"]
        samples.append(f"- {name}: " + ", ".join(f"{k}={v}" for k, v in first.items() if v not in (None, [], "")))

    print(f"문장 {len(sentences)}개 × 구성 {len(configs)}개 (조건 분해 요청 = 코스 1개 만들 때 1회)\n")
    print("| 모델 · effort | 입력 토큰 | 출력 토큰(생각 포함) | 평균 지연 | 성공 | 1회 비용 | 1,000회 비용 | 오류 |")
    print("|---|---|---|---|---|---|---|---|")
    print("\n".join(rows))
    print(f"\n첫 문장 해석 비교: {sentences[0]}")
    print("\n".join(samples))


if __name__ == "__main__":
    asyncio.run(main())
