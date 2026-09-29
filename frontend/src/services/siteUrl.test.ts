import { afterEach, describe, expect, it, vi } from "vitest";

import { siteOrigin } from "./siteUrl";

const h = (m: Record<string, string>) => ({ get: (k: string) => m[k.toLowerCase()] ?? null });

describe("사이트 주소(미리보기 절대 URL)", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("프록시가 넘긴 호스트·프로토콜을 쓴다", () => {
    expect(siteOrigin(h({ host: "frontend:3000", "x-forwarded-host": "date.example", "x-forwarded-proto": "https" }))?.href)
      .toBe("https://date.example/");
  });

  it("프로토콜이 없으면 배포는 https, 로컬은 http", () => {
    expect(siteOrigin(h({ host: "date.example" }))?.href).toBe("https://date.example/");
    expect(siteOrigin(h({ host: "localhost:3000" }))?.href).toBe("http://localhost:3000/");
  });

  it("SITE_URL 이 있으면 그 값이 먼저다", () => {
    vi.stubEnv("SITE_URL", "https://coursepilot.example");
    expect(siteOrigin(h({ host: "evil.example" }))?.href).toBe("https://coursepilot.example/");
  });

  it("모양이 이상한 호스트는 쓰지 않는다", () => {
    expect(siteOrigin(h({ host: "evil.example/<script>" }))).toBeUndefined();
    expect(siteOrigin(h({}))).toBeUndefined();
    expect(siteOrigin(null)).toBeUndefined();
  });
});
