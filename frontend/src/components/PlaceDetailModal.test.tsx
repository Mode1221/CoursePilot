import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PlaceDetailModal from "./PlaceDetailModal";
import type { Place } from "@/types";

const addPlace = vi.fn();
let mockCourse: { items: { place: Place }[] } | null = null;

vi.mock("@/store/courseStore", () => ({
  useCourseStore: (sel: (s: Record<string, unknown>) => unknown) =>
    sel({ addPlace, course: mockCourse }),
}));

const relatedPlaces = vi.fn();
const ratePlace = vi.fn().mockResolvedValue({ ok: true, average: 5 });
const revisit = vi.fn().mockResolvedValue({ ok: true });

vi.mock("@/services/api", () => ({
  api: {
    reviewSummary: () =>
      Promise.resolve({ summary: "요약", count: 2, pros: ["분위기"], cons: ["웨이팅"] }),
    relatedPlaces: (...a: unknown[]) => relatedPlaces(...a),
    ratePlace: (...a: unknown[]) => ratePlace(...a),
    revisit: (...a: unknown[]) => revisit(...a),
  },
}));

const place: Place = { id: "p1", name: "장소1", category: "카페", lat: 37.5, lng: 127.0 };

describe("PlaceDetailModal", () => {
  beforeEach(() => {
    mockCourse = null;
    addPlace.mockClear();
    relatedPlaces.mockReset();
  });
  afterEach(() => cleanup());

  it("함께 가요 추천을 렌더하고 편집 가능 시 추가 버튼으로 addPlace 호출", async () => {
    relatedPlaces.mockResolvedValue([{ id: "r1", name: "관련장소", category: "바", lat: 37.5, lng: 127.0 }]);
    const onClose = vi.fn();
    const { getByText } = render(<PlaceDetailModal place={place} onClose={onClose} editable />);
    await waitFor(() => getByText(/관련장소/));
    fireEvent.click(getByText("추가"));
    expect(addPlace).toHaveBeenCalledWith("r1");
    expect(onClose).toHaveBeenCalled();
  });

  it("editable=false면 추가 버튼을 노출하지 않는다", async () => {
    relatedPlaces.mockResolvedValue([{ id: "r1", name: "관련장소", lat: 37.5, lng: 127.0 }]);
    const { getByText, queryByText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} />);
    await waitFor(() => getByText(/관련장소/));
    expect(queryByText("추가")).toBeNull();
  });

  it("별점 클릭 시 ratePlace 호출", async () => {
    relatedPlaces.mockResolvedValue([]);
    const { getByLabelText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} />);
    fireEvent.click(getByLabelText("4점"));
    expect(ratePlace).toHaveBeenCalledWith("p1", 4, undefined);
  });

  it("또 가고 싶어요 클릭 시 revisit 호출", async () => {
    relatedPlaces.mockResolvedValue([]);
    const { getByText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} />);
    fireEvent.click(getByText("또 가고 싶어요"));
    expect(revisit).toHaveBeenCalledWith("p1", undefined);
  });

  it("리뷰 애스펙트를 좋은 점/주의할 점 뱃지로 보여준다", async () => {
    relatedPlaces.mockResolvedValue([]);
    const { getByText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} />);
    await waitFor(() => getByText(/분위기/));
    expect(getByText(/웨이팅/)).toBeTruthy();
  });

  it("이미 코스에 있는 추천 장소는 추가할 수 없다", async () => {
    mockCourse = { items: [{ place: { id: "r1", name: "관련장소", lat: 37.5, lng: 127 } }] };
    relatedPlaces.mockResolvedValue([{ id: "r1", name: "관련장소", lat: 37.5, lng: 127.0 }]);
    const { getByText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} editable />);
    await waitFor(() => getByText(/관련장소/));
    expect((getByText("추가됨") as HTMLButtonElement).disabled).toBe(true);
  });

  it("별점 저장이 실패하면 이전 상태로 되돌린다", async () => {
    relatedPlaces.mockResolvedValue([]);
    ratePlace.mockRejectedValueOnce(new Error("boom"));
    const { getByLabelText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} />);
    fireEvent.click(getByLabelText("4점"));
    await waitFor(() => expect(ratePlace).toHaveBeenCalled());
    // 실패 후에는 "평가 감사합니다!" 문구가 남지 않는다
    await waitFor(() => expect(document.body.textContent).not.toContain("평가 감사합니다"));
  });

  it("사실 태그와 평가 수·업력·확인 필요를 표시한다", async () => {
    relatedPlaces.mockResolvedValue([]);
    const detailed: Place = {
      ...place,
      rating: 4.3,
      rating_count: 812,
      opened_on: "2015-03-01",
      hours_unverified: true,
      fact_tags: ["주차"],
      caution_tags: ["단체석"],
    };
    const { getByText } = render(<PlaceDetailModal place={detailed} onClose={() => {}} />);
    await waitFor(() => getByText(/812/));
    getByText("주차 가능");
    getByText("단체석 주의");
    getByText(/년차/);
    getByText(/영업시간 확인 필요/);
  });
});
