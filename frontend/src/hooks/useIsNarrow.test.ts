import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useIsNarrow } from "./useIsNarrow";

afterEach(() => vi.unstubAllGlobals());

function stubMatchMedia(matches: boolean) {
  const listeners: Array<() => void> = [];
  const mq = {
    matches,
    addEventListener: (_: string, fn: () => void) => listeners.push(fn),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("matchMedia", () => mq);
  return { mq, fire: () => listeners.forEach((fn) => fn()) };
}

describe("좁은 화면 감지", () => {
  it("초기 미디어 쿼리 결과를 반영한다", () => {
    stubMatchMedia(true);
    const { result } = renderHook(() => useIsNarrow());
    expect(result.current).toBe(true);
  });

  it("화면을 넓히면 다시 데스크톱 레이아웃으로 돌아온다", () => {
    const { mq, fire } = stubMatchMedia(true);
    const { result } = renderHook(() => useIsNarrow());
    act(() => {
      mq.matches = false;
      fire();
    });
    expect(result.current).toBe(false);
  });

  it("언마운트 시 리스너를 정리한다", () => {
    const { mq } = stubMatchMedia(false);
    const { unmount } = renderHook(() => useIsNarrow());
    unmount();
    expect(mq.removeEventListener).toHaveBeenCalled();
  });
});
