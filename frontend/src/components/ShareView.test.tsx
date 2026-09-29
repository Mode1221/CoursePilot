import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ShareView from "./ShareView";
import { useCourseStore } from "@/store/courseStore";

vi.mock("@/services/api", () => ({
  api: {
    getCourse: vi.fn(),
    view: vi.fn().mockResolvedValue(undefined),
    addBookmark: vi.fn(),
  },
}));

vi.mock("@/components/MapPanel", () => ({
  default: () => <div data-testid="map-panel" />,
}));

const { api } = await import("@/services/api");

const course = {
  id: "c1",
  title: "성수동 데이트",
  region: "성수동",
  plan_date: "2026-09-12",
  party_size: 2,
  items: [],
  locked: false,
};

describe("ShareView", () => {
  beforeEach(() => {
    cleanup();
    useCourseStore.setState({ course: null, notFound: false });
    vi.mocked(api.getCourse).mockResolvedValue(course as never);
  });

  it("코스 제목과 날짜·인원·지역을 보여준다", async () => {
    render(<ShareView id="c1" />);
    await waitFor(() => expect(screen.getByText("성수동 데이트")).toBeTruthy());
    expect(screen.getByText("9월 12일 (토) · 2명 · 성수동")).toBeTruthy();
  });

  it("제목이 없으면 기본 문구를 보여준다", async () => {
    vi.mocked(api.getCourse).mockResolvedValue({ ...course, title: "" } as never);
    render(<ShareView id="c2" />);
    await waitFor(() => expect(screen.getByText("공유된 코스")).toBeTruthy());
  });
});
