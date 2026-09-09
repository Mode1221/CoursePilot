import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("ApiError", () => {
  it("추적 id 를 함께 담는다", () => {
    const err = new ApiError(500, "서버 오류", "abc123");
    expect(err.status).toBe(500);
    expect(err.requestId).toBe("abc123");
  });

  it("추적 id 는 선택 값이다", () => {
    expect(new ApiError(404, "없음").requestId).toBeUndefined();
  });
});

function stubResponse(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      headers: { get: () => null },
      json: async () => body,
      text: async () => JSON.stringify(body),
    }),
  );
}

describe("요청 오류 메시지", () => {
  it("서버가 준 한국어 detail 을 그대로 쓴다", async () => {
    stubResponse(404, { detail: "코스를 찾을 수 없어요" });
    await expect(api.getCourse("c1")).rejects.toThrow("코스를 찾을 수 없어요");
  });

  it("detail 이 없으면 내부 경로 대신 안내 문구를 쓴다", async () => {
    stubResponse(500, {});
    await expect(api.getCourse("c1")).rejects.toThrow(/다시 시도해주세요/);
  });

  it("검증 오류(배열 detail)도 사람이 읽을 수 있게 바꾼다", async () => {
    stubResponse(422, { detail: [{ loc: ["body", "text"], msg: "too long" }] });
    await expect(api.getCourse("c1")).rejects.toThrow(/다시 시도해주세요/);
  });
});
