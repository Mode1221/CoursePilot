import { beforeEach, describe, expect, it } from "vitest";

import { storedUserId, useUserStore } from "./userStore";

const KEY = "coursepilot_user_id";

describe("userStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useUserStore.setState({ userId: null, questionsLeft: null });
  });

  it("setUser는 상태와 localStorage에 기록한다", () => {
    useUserStore.getState().setUser("u1");
    expect(useUserStore.getState().userId).toBe("u1");
    expect(localStorage.getItem(KEY)).toBe("u1");
  });

  it("load는 localStorage에서 세션을 복원한다", () => {
    localStorage.setItem(KEY, "u2");
    useUserStore.getState().load();
    expect(useUserStore.getState().userId).toBe("u2");
  });

  it("load는 값이 없으면 userId를 유지한다(null)", () => {
    useUserStore.getState().load();
    expect(useUserStore.getState().userId).toBeNull();
  });
});

it("storedUserId 는 스토어 로드 전에도 저장된 id 를 준다", () => {
  window.localStorage.setItem("coursepilot_user_id", "u-stored");
  expect(storedUserId()).toBe("u-stored");
  window.localStorage.removeItem("coursepilot_user_id");
  expect(storedUserId()).toBeNull();
});
