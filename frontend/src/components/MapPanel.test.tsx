import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MapPanel from "./MapPanel";
import { useCourseStore } from "@/store/courseStore";

vi.mock("@/services/api", () => ({
  api: {
    searchPlaces: vi.fn(),
    addPlace: vi.fn(),
    setItems: vi.fn(),
    reorder: vi.fn(),
    courseReasons: vi.fn(),
  },
}));

function setCourse(overrides: Record<string, unknown> = {}) {
  useCourseStore.setState({
    course: {
      id: "c1",
      title: "성수 코스",
      region: "성수동",
      items: [
        {
          place: { id: "p1", name: "카페 A", category: "cafe", lat: 37.5, lng: 127, price: 15000 },
          arrive: "13:00:00",
          depart: "14:00:00",
          travel_to_next: {
            from_place_id: "p1",
            to_place_id: "p2",
            mode: "transit",
            duration_min: 15,
            distance_m: 3000,
          },
        },
        {
          place: { id: "p2", name: "전시 B", category: "gallery", lat: 37.51, lng: 127.01 },
          arrive: "14:15:00",
          depart: "16:00:00",
          travel_to_next: null,
        },
      ],
      locked: false,
      ...overrides,
    },
    locked: false,
    history: [],
  } as never);
}

describe("MapPanel", () => {
  beforeEach(async () => {
    const { api } = await import("@/services/api");
    vi.mocked(api.courseReasons).mockResolvedValue({ reasons: {} } as never);
    setCourse();
  });
  afterEach(cleanup);

  it("타임라인 순번·시간과 구간 이동수단을 보여준다", () => {
    render(<MapPanel />);
    expect(screen.getByText("1. 카페 A")).toBeDefined();
    expect(screen.getByText("13:00~14:00")).toBeDefined();
    expect(screen.getByText(/다음까지 15분 \(대중교통\)/)).toBeDefined();
  });

  it("가격이 있는 장소만 1인 예상 비용을 표시한다", () => {
    render(<MapPanel />);
    expect(screen.getAllByText("1.5만원").length).toBe(1);
  });

  it("공유 뷰(readOnly)에서는 편집 버튼을 감춘다", () => {
    render(<MapPanel readOnly />);
    expect(screen.queryByLabelText("카페 A 삭제")).toBeNull();
    expect(screen.getAllByLabelText(/지도에서 보기|지도에서 보기/).length).toBeGreaterThan(0);
  });
  it("장소 선택 근거를 카드에 보여준다", async () => {
    const { api } = await import("@/services/api");
    vi.mocked(api.courseReasons).mockResolvedValue({
      reasons: { p1: ["'조용한' 조건에 맞아요", "평점 4.6"] },
    } as never);
    setCourse();
    render(<MapPanel />);
    await waitFor(() =>
      expect(screen.getByText("'조용한' 조건에 맞아요 · 평점 4.6")).toBeTruthy(),
    );
  });

});
