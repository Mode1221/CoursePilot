import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CourseTitle from "./CourseTitle";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";

vi.mock("@/services/api", () => ({ api: { renameCourse: vi.fn() } }));

describe("CourseTitle", () => {
  beforeEach(() => {
    vi.mocked(api.renameCourse).mockReset();
    useCourseStore.setState({ course: null, history: [] });
  });
  afterEach(cleanup);

  it("클릭하면 편집 모드로 바뀌고 저장 시 PATCH 한다", async () => {
    vi.mocked(api.renameCourse).mockResolvedValue({
      id: "c1",
      title: "성수 데이트",
      items: [],
      locked: false,
    });
    render(<CourseTitle courseId="c1" title="새 코스" userId="u1" />);
    fireEvent.click(screen.getByLabelText("코스 이름 편집"));
    fireEvent.change(screen.getByLabelText("코스 이름"), { target: { value: "성수 데이트" } });
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(api.renameCourse).toHaveBeenCalledWith("c1", "성수 데이트", "u1"));
    expect(useCourseStore.getState().course?.title).toBe("성수 데이트");
  });

  it("이름이 그대로면 저장하지 않는다", async () => {
    render(<CourseTitle courseId="c1" title="새 코스" />);
    fireEvent.click(screen.getByLabelText("코스 이름 편집"));
    fireEvent.keyDown(screen.getByLabelText("코스 이름"), { key: "Enter" });
    expect(api.renameCourse).not.toHaveBeenCalled();
  });

  it("Escape 로 편집을 취소한다", () => {
    render(<CourseTitle courseId="c1" title="새 코스" />);
    fireEvent.click(screen.getByLabelText("코스 이름 편집"));
    fireEvent.keyDown(screen.getByLabelText("코스 이름"), { key: "Escape" });
    expect(screen.getByLabelText("코스 이름 편집")).toBeTruthy();
  });
});
