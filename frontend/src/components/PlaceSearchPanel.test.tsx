import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PlaceSearchPanel from "./PlaceSearchPanel";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";

vi.mock("@/services/api", () => ({
  api: { searchPlaces: vi.fn(), addPlace: vi.fn(), setItems: vi.fn() },
}));
// 상세 모달은 별도 테스트가 있다 — 여기선 열리는지만 본다
vi.mock("@/components/PlaceDetailModal", () => ({
  default: ({ place, onClose }: { place: { name: string }; onClose: () => void }) => (
    <div role="dialog" aria-label={`${place.name} 상세`}>
      <button onClick={onClose}>닫기</button>
    </div>
  ),
}));

describe("PlaceSearchPanel", () => {
  beforeEach(() => {
    vi.mocked(api.searchPlaces).mockReset();
    vi.mocked(api.addPlace).mockReset();
    useCourseStore.setState({
      course: {
        id: "c1",
        title: "t",
        region: "성수동",
        items: [{ place: { id: "p1", name: "이미있음", lat: 37.5, lng: 127 }, travel_to_next: null }],
        locked: false,
      },
      locked: false,
      history: [],
    });
  });

  afterEach(cleanup);

  it("검색 결과를 보여주고 추가할 수 있다", async () => {
    vi.mocked(api.searchPlaces).mockResolvedValue([
      { id: "p2", name: "새 카페", lat: 37.5, lng: 127 },
    ]);
    vi.mocked(api.addPlace).mockResolvedValue({
      id: "c1",
      title: "t",
      items: [],
      locked: false,
    });

    render(<PlaceSearchPanel />);
    fireEvent.click(screen.getByText("+ 장소 직접 추가"));
    fireEvent.change(screen.getByLabelText("장소 검색어"), { target: { value: "카페" } });
    fireEvent.click(screen.getByRole("button", { name: "검색" }));

    await waitFor(() => expect(screen.queryByText("새 카페")).not.toBeNull());
    expect(api.searchPlaces).toHaveBeenCalledWith("성수동", "카페");

    fireEvent.click(screen.getByText("추가"));
    await waitFor(() => expect(api.addPlace).toHaveBeenCalledWith("c1", "p2"));
  });

  it("이미 코스에 있는 장소는 추가 버튼이 비활성", async () => {
    vi.mocked(api.searchPlaces).mockResolvedValue([
      { id: "p1", name: "이미있음", lat: 37.5, lng: 127 },
    ]);
    render(<PlaceSearchPanel />);
    fireEvent.click(screen.getByText("+ 장소 직접 추가"));
    fireEvent.click(screen.getByRole("button", { name: "검색" }));
    await waitFor(() =>
      expect((screen.getByText("추가됨") as HTMLButtonElement).disabled).toBe(true),
    );
  });

  it("검색된 가게 이름을 누르면 추가하기 전에 정보 팝업을 연다", async () => {
    vi.mocked(api.searchPlaces).mockResolvedValue([{ id: "p2", name: "새 카페", lat: 37.5, lng: 127 }]);
    render(<PlaceSearchPanel />);
    fireEvent.click(screen.getByText("+ 장소 직접 추가"));
    fireEvent.change(screen.getByLabelText("장소 검색어"), { target: { value: "카페" } });
    fireEvent.click(screen.getByRole("button", { name: "검색" }));
    await waitFor(() => expect(screen.queryByText("새 카페")).not.toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "새 카페 정보 보기" }));
    expect(await screen.findByRole("dialog", { name: "새 카페 상세" })).toBeTruthy();
    expect(api.addPlace).not.toHaveBeenCalled(); // 이름을 눌렀다고 추가되진 않는다
    fireEvent.click(screen.getByText("닫기"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
