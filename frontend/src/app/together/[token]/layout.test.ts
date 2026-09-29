import { afterEach, describe, expect, it, vi } from "vitest";

import { generateMetadata } from "./layout";

// 미리보기 이미지 절대 주소는 요청 호스트로 만든다(siteUrl.ts)
vi.mock("next/headers", () => ({
  headers: async () => new Headers({ host: "frontend:3000", "x-forwarded-host": "date.example" }),
}));

afterEach(() => vi.unstubAllGlobals());

describe("같이 정하기 링크 미리보기", () => {
  it("열람으로 세지 않는 미리보기 조회로 제목을 채운다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ owner_name: "민수", request_text: "토요일 3시 성수", built: false }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const meta = await generateMetadata({ params: Promise.resolve({ token: "tok_123456" }) });
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/together\/tok_123456\/preview$/);
    expect(meta.title).toBe("민수님이 데이트 코스를 같이 정하자고 해요");
    expect(meta.openGraph?.description).toMatch(/토요일 3시 성수/);
    expect(String(meta.metadataBase)).toBe("https://date.example/");
  });

  it("토큰이 틀리면(404) 일반 초대 문구", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));
    const meta = await generateMetadata({ params: Promise.resolve({ token: "nope" }) });
    expect(meta.title).toBe("같이 데이트 코스 정하기 — 픽앤어스");
    expect(meta.openGraph?.title).toBe("같이 데이트 코스 정하기 — 픽앤어스");
  });

  it("백엔드가 죽어 있어도 렌더한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    const meta = await generateMetadata({ params: Promise.resolve({ token: "tok" }) });
    expect(meta.title).toBe("같이 데이트 코스 정하기 — 픽앤어스");
  });
});
