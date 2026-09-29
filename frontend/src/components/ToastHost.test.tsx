import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ToastHost from "./ToastHost";
import { toast, useToastStore } from "@/store/toastStore";

describe("ToastHost", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useToastStore.setState({ toasts: [] });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("토스트를 렌더하고 일정 시간 뒤 사라진다", () => {
    render(<ToastHost />);
    act(() => toast("저장하지 못했어요", "error"));
    expect(screen.getByText("저장하지 못했어요")).toBeTruthy();

    act(() => vi.advanceTimersByTime(4000));
    expect(screen.queryByText("저장하지 못했어요")).toBeNull();
  });

  it("클릭하면 즉시 닫힌다", () => {
    render(<ToastHost />);
    act(() => toast("복사했어요", "success"));
    fireEvent.click(screen.getByText("복사했어요"));
    expect(screen.queryByText("복사했어요")).toBeNull();
  });

  it("최대 3개까지만 유지한다", () => {
    act(() => {
      toast("1");
      toast("2");
      toast("3");
      toast("4");
    });
    expect(useToastStore.getState().toasts.map((t) => t.text)).toEqual(["2", "3", "4"]);
  });
});
