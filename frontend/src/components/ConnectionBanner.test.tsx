import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import ConnectionBanner from "./ConnectionBanner";
import { useCourseStore } from "@/store/courseStore";

afterEach(cleanup);

describe("ConnectionBanner", () => {
  it("연결이 끊기면 안내한다", () => {
    useCourseStore.setState({ connected: false, viewers: 1 });
    render(<ConnectionBanner />);
    expect(screen.getByRole("status").textContent).toContain("실시간 연결이 끊겼습니다");
  });

  it("혼자 보고 있으면 아무것도 보여주지 않는다", () => {
    useCourseStore.setState({ connected: true, viewers: 1 });
    const { container } = render(<ConnectionBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("함께 보는 사람이 있으면 인원수를 알린다", () => {
    useCourseStore.setState({ connected: true, viewers: 3 });
    render(<ConnectionBanner />);
    expect(screen.getByRole("status").textContent).toContain("3명이 이 코스를 함께");
  });
});
