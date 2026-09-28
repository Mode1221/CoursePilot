import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TogetherPanel from "./TogetherPanel";
import { useCourseStore } from "@/store/courseStore";
import { useUserStore } from "@/store/userStore";

vi.mock("@/services/api", () => ({ api: { togetherLink: vi.fn(), togetherStatus: vi.fn() } }));

function setup(items: unknown[]) {
  useUserStore.setState({ userId: "u1" } as never);
  useCourseStore.setState({ course: { id: "c1", title: "t", items } } as never);
  render(<TogetherPanel courseId="c1" />);
}

describe("TogetherPanel", () => {
  afterEach(cleanup);

  it("코스가 없으면 바로 입력 박스를 보여 준다", () => {
    setup([]);
    expect(screen.getByLabelText("내 이름")).toBeTruthy();
  });

  it("코스가 있으면 한 줄로 접고, 누르면 펼친다", () => {
    setup([{ place: { id: "p1", name: "A", lat: 0, lng: 0 } }]);
    expect(screen.queryByLabelText("내 이름")).toBeNull(); // 첫 화면에 코스가 보이게
    fireEvent.click(screen.getByRole("button", { name: "상대에게 물어보기" }));
    expect(screen.getByLabelText("내 이름")).toBeTruthy();
  });
});
