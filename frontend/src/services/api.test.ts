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

describe("일시적 실패 복구", () => {
  it("조회는 서버 오류 뒤 한 번 다시 시도한다", async () => {
    const ok = {
      ok: true,
      status: 200,
      headers: { get: () => null },
      text: async () => JSON.stringify({ id: "c1" }),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        headers: { get: () => null },
        json: async () => ({}),
        text: async () => "{}",
      })
      .mockResolvedValueOnce(ok);
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getCourse("c1")).resolves.toEqual({ id: "c1" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("쓰기 요청은 다시 시도하지 않는다(중복 생성 방지)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: { get: () => null },
      json: async () => ({}),
      text: async () => "{}",
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.generate("c1", "성수동")).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("응답이 없으면 타임아웃 문구로 끝난다(무한 대기 금지)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("timeout", "TimeoutError")),
    );
    await expect(api.generate("c1", "성수동")).rejects.toThrow(/응답이 너무 늦어요/);
  });
});
