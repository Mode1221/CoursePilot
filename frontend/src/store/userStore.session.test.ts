import { beforeEach, describe, expect, it } from "vitest";

import { storedUserToken, useUserStore } from "./userStore";

describe("세션 토큰", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useUserStore.setState({ userId: null, questionsLeft: null });
  });

  it("가입 시 받은 토큰을 저장한다", () => {
    useUserStore.getState().setUser("u1", "sig-1");
    expect(storedUserToken()).toBe("sig-1");
  });

  it("토큰이 없는 서버(개발)에서는 이전 토큰을 지운다", () => {
    useUserStore.getState().setUser("u1", "sig-1");
    useUserStore.getState().setUser("u2");
    expect(storedUserToken()).toBeNull();
  });

  it("로그아웃하면 토큰도 지운다", () => {
    useUserStore.getState().setUser("u1", "sig-1");
    useUserStore.getState().clearUser();
    expect(storedUserToken()).toBeNull();
    expect(useUserStore.getState().userId).toBeNull();
  });
});
