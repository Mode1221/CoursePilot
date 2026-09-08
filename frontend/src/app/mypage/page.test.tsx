import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MyPage from "./page";
import { api } from "@/services/api";
import { useUserStore } from "@/store/userStore";

vi.mock("@/services/api", () => ({
  api: {
    myCourses: vi.fn(),
    myBookmarks: vi.fn(),
    duplicateCourse: vi.fn(),
    renameCourse: vi.fn(),
    deleteCourse: vi.fn(),
  },
}));

const COURSE = { id: "c1", title: "성수 코스", region: "성수동", items: [], locked: false };

describe("마이페이지", () => {
  beforeEach(() => {
    vi.mocked(api.myCourses).mockResolvedValue([COURSE] as never);
    vi.mocked(api.myBookmarks).mockResolvedValue([]);
    vi.mocked(api.duplicateCourse).mockResolvedValue({
      ...COURSE,
      id: "c2",
      title: "성수 코스 (사본)",
    } as never);
    useUserStore.setState({ userId: "u1" } as never);
  });

  afterEach(cleanup);

  it("로그인 상태면 내 코스를 사용자 헤더와 함께 불러온다", async () => {
    render(<MyPage />);
    await waitFor(() => expect(api.myCourses).toHaveBeenCalledWith("u1"));
    expect(await screen.findByText("성수 코스")).toBeDefined();
  });

  it("복제 버튼을 누르면 사본이 목록에 추가된다", async () => {
    render(<MyPage />);
    const button = await screen.findByLabelText("성수 코스 복제");
    fireEvent.click(button);
    await waitFor(() => expect(api.duplicateCourse).toHaveBeenCalledWith("c1", "u1"));
    expect(await screen.findByText("성수 코스 (사본)")).toBeDefined();
  });

  it("비로그인 상태면 가입을 안내한다", () => {
    useUserStore.setState({ userId: null } as never);
    render(<MyPage />);
    expect(screen.getByText("로그인이 필요해요")).toBeDefined();
  });
});
