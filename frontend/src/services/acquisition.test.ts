import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  INVITE_TTL_MS,
  arrivalPayload,
  captureAcquisition,
  clearAcquisition,
  inviteTokenFromPath,
  isFirstVisit,
  readAcquisition,
  rememberInvite,
  reportVisit,
  sanitizeSource,
} from "./acquisition";

describe("유입 경로 기억", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("출처는 소문자·[a-z0-9_-]·32자로 정리한다(서버와 같은 규칙)", () => {
    expect(sanitizeSource("Instagram")).toBe("instagram");
    expect(sanitizeSource("  Kakao Talk! ")).toBe("kakaotalk");
    expect(sanitizeSource("threads_ad-01")).toBe("threads_ad-01");
    expect(sanitizeSource("인스타")).toBeUndefined();
    expect(sanitizeSource("")).toBeUndefined();
    expect(sanitizeSource(null)).toBeUndefined();
    expect(sanitizeSource("a".repeat(50))).toBe("a".repeat(32));
  });

  it("src 가 utm_source 보다 먼저고, 캠페인도 남긴다", () => {
    captureAcquisition("?src=Threads&utm_source=google&utm_campaign=Fall%202026", "/", 1);
    expect(arrivalPayload(2)).toEqual({ source: "threads", campaign: "fall2026" });
  });

  it("utm_source 만 있어도 쓴다", () => {
    captureAcquisition("?utm_source=naver", "/", 1);
    expect(arrivalPayload(2)).toEqual({ source: "naver" });
  });

  it("첫 방문만 기억한다(나중 광고 링크로 덮어쓰지 않는다)", () => {
    captureAcquisition("?src=instagram", "/", 1);
    captureAcquisition("?src=naver", "/", 2);
    expect(arrivalPayload(3).source).toBe("instagram");

    localStorage.clear();
    captureAcquisition("", "/", 1); // 출처 없이 온 첫 방문
    captureAcquisition("?src=naver", "/", 2);
    expect(arrivalPayload(3).source).toBeUndefined();
  });

  it("같이 정하기 링크로 오면 토큰을 기억한다(처음 받은 초대가 이긴다)", () => {
    captureAcquisition("", "/together/AbC_def-123456", 1);
    rememberInvite("zzzzzzzzzzzzzzzz", 2);
    expect(arrivalPayload(3)).toEqual({ invite: "AbC_def-123456" });
    expect(readAcquisition().at).toBe(1);
  });

  it("먼저 광고로 왔다가 나중에 초대를 받아도 출처는 지키고 토큰은 더한다", () => {
    captureAcquisition("?src=instagram", "/", 1);
    rememberInvite("AbC_def-123456", 2);
    expect(arrivalPayload(3)).toEqual({ source: "instagram", invite: "AbC_def-123456" });
  });

  it("오래된 초대 토큰은 보내지 않는다", () => {
    rememberInvite("AbC_def-123456", 1);
    expect(arrivalPayload(1 + INVITE_TTL_MS + 1).invite).toBeUndefined();
  });

  it("같이 정하기 경로만 토큰으로 본다", () => {
    expect(inviteTokenFromPath("/together/AbC_def-123456")).toBe("AbC_def-123456");
    expect(inviteTokenFromPath("/together/AbC_def-123456/")).toBe("AbC_def-123456");
    expect(inviteTokenFromPath("/together/short")).toBeUndefined();
    expect(inviteTokenFromPath("/share/AbC_def-123456")).toBeUndefined();
    expect(inviteTokenFromPath("/together/bad%20token!!")).toBeUndefined();
  });

  it("저장소가 막혀도 깨지지 않는다", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => captureAcquisition("?src=x", "/together/AbC_def-123456")).not.toThrow();
    expect(arrivalPayload()).toEqual({});
    expect(() => clearAcquisition()).not.toThrow();
  });

  it("깨진 저장값은 없는 것으로 본다", () => {
    localStorage.setItem("coursepilot_acq", "{not json");
    expect(readAcquisition()).toEqual({});
    captureAcquisition("?src=kakao", "/", 1);
    expect(arrivalPayload(2).source).toBe("kakao");
  });

  it("회원이 되면 지운다", () => {
    captureAcquisition("?src=kakao", "/together/AbC_def-123456", 1);
    clearAcquisition();
    expect(arrivalPayload(2)).toEqual({});
  });
});

describe("첫 방문 알리기", () => {
  beforeEach(() => localStorage.clear());

  it("기기의 첫 방문만 첫 방문이다", () => {
    expect(isFirstVisit()).toBe(true);
    captureAcquisition("?src=threads", "/", 1);
    expect(isFirstVisit()).toBe(false);
  });

  it("출처를 담아 /visit 로 한 번 보내고, 실패해도 던지지 않는다", async () => {
    const send = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    reportVisit("threads", send as unknown as typeof fetch);
    expect(send).toHaveBeenCalledTimes(1);
    const [url, init] = send.mock.calls[0];
    expect(String(url)).toMatch(/\/visit$/);
    expect(JSON.parse(init.body)).toEqual({ source: "threads" });
    expect(init.keepalive).toBe(true);
    const failing = vi.fn().mockRejectedValue(new Error("offline"));
    expect(() => reportVisit(undefined, failing as unknown as typeof fetch)).not.toThrow();
    expect(JSON.parse(failing.mock.calls[0][1].body)).toEqual({});
  });
});
