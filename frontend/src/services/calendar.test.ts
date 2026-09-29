import { afterEach, describe, expect, it, vi } from "vitest";

import { saveCalendar } from "./calendar";
import { useToastStore } from "@/store/toastStore";

afterEach(() => {
  vi.restoreAllMocks();
  useToastStore.setState({ toasts: [] });
});

describe("캘린더 저장", () => {
  it("코스 ics 링크를 눌러 내려받고 흔적을 남기지 않는다", () => {
    const click = vi.fn();
    const anchor = document.createElement("a");
    anchor.click = click;
    vi.spyOn(document, "createElement").mockReturnValue(anchor);

    saveCalendar("c1");

    expect(anchor.href).toMatch(/\/courses\/c1\/calendar\.ics$/);
    expect(anchor.download).toBe("coursepilot-c1.ics");
    expect(click).toHaveBeenCalled();
    expect(document.body.contains(anchor)).toBe(false);
    expect(useToastStore.getState().toasts[0].tone).toBe("success");
  });

  it("저장에 실패하면 실패를 알린다", () => {
    vi.spyOn(document, "createElement").mockImplementation(() => {
      throw new Error("불가");
    });
    saveCalendar("c1");
    expect(useToastStore.getState().toasts[0].tone).toBe("error");
  });
});
