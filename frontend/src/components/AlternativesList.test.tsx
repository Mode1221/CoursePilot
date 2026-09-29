import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AlternativesList from "./AlternativesList";

afterEach(cleanup);

describe("AlternativesList", () => {
  const items = [
    { id: "a", name: "삼겹집", category: "음식점 > 고기", lat: 0, lng: 0, hot_reasons: ["최근 검색량 증가"] },
    { id: "b", name: "파스타집", category: "음식점 > 양식", lat: 0, lng: 0 },
  ];

  it("대안을 고르면 그 장소로, 직접 찾기는 검색으로", () => {
    const onPick = vi.fn();
    const onSearch = vi.fn();
    render(<AlternativesList items={items} onPick={onPick} onSearch={onSearch} />);
    expect(screen.getByText(/🔥 최근 검색량 증가/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "파스타집(으)로 바꾸기" }));
    expect(onPick).toHaveBeenCalledWith(items[1]);
    fireEvent.click(screen.getByText("직접 찾기"));
    expect(onSearch).toHaveBeenCalled();
  });
});
