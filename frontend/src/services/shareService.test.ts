import { afterEach, describe, expect, it, vi } from "vitest";

import { shareService } from "./shareService";
import { useToastStore } from "@/store/toastStore";

afterEach(() => {
  vi.unstubAllGlobals();
  useToastStore.setState({ toasts: [] });
});

function stubNavigator(nav: Record<string, unknown>) {
  vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0", ...nav });
}

describe("공유 어댑터", () => {
  it("Web Share API 가 있으면 그것을 쓴다", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    stubNavigator({ share });
    await shareService.share("https://cp/c1");
    expect(share).toHaveBeenCalledWith({ title: "CoursePilot 코스", url: "https://cp/c1" });
  });

  it("공유 시트를 닫아도 조용히 끝난다", async () => {
    stubNavigator({ share: vi.fn().mockRejectedValue(new Error("AbortError")) });
    await expect(shareService.share("https://cp/c1")).resolves.toBeUndefined();
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("Web Share 가 없으면 클립보드로 복사하고 알린다", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubNavigator({ clipboard: { writeText } });
    await shareService.share("https://cp/c1");
    expect(writeText).toHaveBeenCalledWith("https://cp/c1");
    expect(useToastStore.getState().toasts[0].tone).toBe("success");
  });

  it("복사도 실패하면 주소창을 안내한다", async () => {
    stubNavigator({ clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) } });
    await shareService.share("https://cp/c1");
    const [t] = useToastStore.getState().toasts;
    expect(t.tone).toBe("error");
    expect(t.text).toMatch(/주소창/);
  });

  it("카카오 인앱에서는 카카오 공유 카드를 쓴다", async () => {
    const sendDefault = vi.fn();
    stubNavigator({ userAgent: "Mozilla/5.0 KAKAOTALK/10.0.0", share: vi.fn() });
    vi.stubGlobal("Kakao", { Share: { sendDefault } });
    await shareService.share("https://cp/c1", "성수동 코스");
    expect(sendDefault).toHaveBeenCalled();
    expect(sendDefault.mock.calls[0][0].content.title).toBe("성수동 코스");
  });
});
