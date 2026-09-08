import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";

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
