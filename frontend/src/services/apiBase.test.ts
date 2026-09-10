import { afterEach, describe, expect, it, vi } from "vitest";

import { apiBase, serverApiBase } from "./apiBase";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function atHost(href: string) {
  const url = new URL(href);
  vi.stubGlobal("window", { location: { protocol: url.protocol, hostname: url.hostname } });
}

describe("API 주소", () => {
  it("배포 도메인에서는 api 서브도메인을 쓴다", () => {
    atHost("https://coursepilot.kr/plan/c1");
    expect(apiBase()).toBe("https://api.coursepilot.kr");
  });

  it("www 는 떼고 붙인다", () => {
    atHost("https://www.coursepilot.kr/");
    expect(apiBase()).toBe("https://api.coursepilot.kr");
  });

  it("로컬 개발은 8000 포트", () => {
    atHost("http://localhost:3000/");
    expect(apiBase()).toBe("http://localhost:8000");
  });

  it("명시 설정이 있으면 그대로 따른다", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "https://staging-api.example.com");
    atHost("https://coursepilot.kr/");
    expect(apiBase()).toBe("https://staging-api.example.com");
  });

  it("SSR 은 컨테이너 내부 주소를 런타임에 읽는다", () => {
    vi.stubEnv("API_INTERNAL_BASE", "http://backend:8000");
    expect(serverApiBase()).toBe("http://backend:8000");
  });

  it("내부 주소가 없으면 로컬로 떨어진다", () => {
    expect(serverApiBase()).toBe("http://localhost:8000");
  });
});
