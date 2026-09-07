import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PlaceDetailModal from "./PlaceDetailModal";
import type { Place } from "@/types";

const addPlace = vi.fn();

vi.mock("@/store/courseStore", () => ({
  useCourseStore: (sel: (s: { addPlace: typeof addPlace }) => unknown) => sel({ addPlace }),
}));

const relatedPlaces = vi.fn();
const ratePlace = vi.fn().mockResolvedValue({ ok: true, average: 5 });
const revisit = vi.fn().mockResolvedValue({ ok: true });

vi.mock("@/services/api", () => ({
  api: {
    reviewSummary: () => Promise.resolve({ summary: "요약", count: 0 }),
    relatedPlaces: (...a: unknown[]) => relatedPlaces(...a),
    ratePlace: (...a: unknown[]) => ratePlace(...a),
    revisit: (...a: unknown[]) => revisit(...a),
  },
}));

const place: Place = { id: "p1", name: "장소1", category: "카페", lat: 37.5, lng: 127.0 };

describe("PlaceDetailModal", () => {
  beforeEach(() => {
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
    expect(ratePlace).toHaveBeenCalledWith("p1", 4);
  });

  it("또 가고 싶어요 클릭 시 revisit 호출", async () => {
    relatedPlaces.mockResolvedValue([]);
    const { getByText } = render(<PlaceDetailModal place={place} onClose={vi.fn()} />);
    fireEvent.click(getByText("또 가고 싶어요"));
    expect(revisit).toHaveBeenCalledWith("p1");
  });
});
