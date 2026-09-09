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
    getPreferences: vi.fn(),
    deleteAccount: vi.fn(),
  },
}));

const COURSE = { id: "c1", title: "성수 코스", region: "성수동", items: [], locked: false };

describe("마이페이지", () => {
  beforeEach(() => {
    vi.mocked(api.myCourses).mockResolvedValue([COURSE] as never);
    vi.mocked(api.myBookmarks).mockResolvedValue([]);
    vi.mocked(api.getPreferences).mockResolvedValue({
      mood: null,
      region: null,
      transport: null,
      budget: null,
      diet: [],
    });
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

  it("저장된 취향을 요약해 보여준다", async () => {
    vi.mocked(api.getPreferences).mockResolvedValue({
      mood: "조용한",
      region: "연남동",
      transport: "도보",
      budget: "2~4만원",
      diet: ["비건"],
    });
    render(<MyPage />);
    await waitFor(() =>
      expect(screen.getByText("내 취향: 연남동 · 조용한 · 도보 · 2~4만원 · 비건")).toBeTruthy(),
    );
  });

  it("취향이 없으면 설정을 권한다", async () => {
    render(<MyPage />);
    await waitFor(() => expect(screen.getByText("취향을 설정하면 추천이 정확해져요.")).toBeTruthy());
  });

  it("회원 탈퇴는 확인을 받고 계정을 삭제한다", async () => {
    vi.mocked(api.deleteAccount).mockResolvedValue({ ok: true, deleted_courses: 2 });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<MyPage />);

    fireEvent.click(screen.getByText("회원 탈퇴"));

    await waitFor(() => expect(api.deleteAccount).toHaveBeenCalledWith("u1"));
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("확인을 취소하면 삭제하지 않는다", () => {
    vi.mocked(api.deleteAccount).mockClear();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<MyPage />);
    fireEvent.click(screen.getByText("회원 탈퇴"));
    expect(api.deleteAccount).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

});
