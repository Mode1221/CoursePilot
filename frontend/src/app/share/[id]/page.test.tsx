import { afterEach, describe, expect, it, vi } from "vitest";

import { generateMetadata } from "./page";

// 미리보기 이미지 절대 주소는 요청 호스트로 만든다(siteUrl.ts)
vi.mock("next/headers", () => ({
  headers: async () => new Headers({ host: "frontend:3000", "x-forwarded-host": "date.example" }),
}));

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
    const meta = await generateMetadata({ params: Promise.resolve({ id: "c1" }) });
    expect(meta.title).toMatch(/성수동 코스/);
    expect(meta.openGraph?.description).toBeTruthy();
  });

  it("백엔드가 죽어 있어도 기본 메타데이터로 렌더한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    const meta = await generateMetadata({ params: Promise.resolve({ id: "c1" }) });
    expect(meta.title).toBe("공유된 코스 — CoursePilot");
    expect(meta.openGraph?.title).toBe("공유된 코스 — CoursePilot");
  });

  it("없는 코스(404)면 일반 미리보기 — 무엇이 없는지 드러내지 않는다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }));
    const meta = await generateMetadata({ params: Promise.resolve({ id: "nope" }) });
    expect(meta.title).toBe("공유된 코스 — CoursePilot");
    expect(String(meta.description)).not.toMatch(/nope/);
  });

  it("응답이 늦으면 기다리지 않고 기본 메타데이터로 간다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("timeout", "TimeoutError")),
    );
    const meta = await generateMetadata({ params: Promise.resolve({ id: "c1" }) });
    expect(meta.title).toBe("공유된 코스 — CoursePilot");
  });
});
