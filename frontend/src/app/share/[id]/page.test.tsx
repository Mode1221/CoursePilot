import { afterEach, describe, expect, it, vi } from "vitest";

import { generateMetadata } from "./page";

afterEach(() => vi.unstubAllGlobals());

describe("공유 페이지 미리보기", () => {
  it("코스를 읽어 제목과 요약을 채운다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: "c1",
          title: "성수동 코스",
          items: [{ place: { id: "p1", name: "카페", lat: 37.5, lng: 127 } }],
        }),
      }),
    );
    const meta = await generateMetadata({ params: { id: "c1" } });
    expect(meta.title).toMatch(/성수동 코스/);
    expect(meta.openGraph?.description).toBeTruthy();
  });

  it("백엔드가 죽어 있어도 기본 메타데이터로 렌더한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    const meta = await generateMetadata({ params: { id: "c1" } });
    expect(meta.title).toBe("공유된 코스 — CoursePilot");
  });

  it("응답이 늦으면 기다리지 않고 기본 메타데이터로 간다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("timeout", "TimeoutError")),
    );
    const meta = await generateMetadata({ params: { id: "c1" } });
    expect(meta.title).toBe("공유된 코스 — CoursePilot");
  });
});
