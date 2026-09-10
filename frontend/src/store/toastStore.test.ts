import { beforeEach, describe, expect, it } from "vitest";

import { toast, useToastStore } from "./toastStore";

beforeEach(() => useToastStore.setState({ toasts: [] }));

describe("토스트 스토어", () => {
  it("서비스 레이어에서도 띄울 수 있다", () => {
    toast("저장 실패", "error");
    expect(useToastStore.getState().toasts[0]).toMatchObject({ text: "저장 실패", tone: "error" });
  });

  it("화면을 가리지 않도록 최근 3개만 남긴다", () => {
    for (let i = 0; i < 5; i++) toast(`알림 ${i}`);
    const texts = useToastStore.getState().toasts.map((t) => t.text);
    expect(texts).toEqual(["알림 2", "알림 3", "알림 4"]);
  });

  it("닫으면 목록에서 빠진다", () => {
    const id = useToastStore.getState().push("안내");
    useToastStore.getState().dismiss(id);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });
});
