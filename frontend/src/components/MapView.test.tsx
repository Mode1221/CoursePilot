import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MapView from "./MapView";
import type { TimelineItem } from "@/types";

function item(id: string, lat: number, lng: number, min?: number): TimelineItem {
  return {
    place: { id, name: id, lat, lng },
    travel_to_next: min ? { from_place_id: id, to_place_id: "x", mode: "walk", duration_min: min, distance_m: 100 } : null,
  };
}

describe("MapView", () => {
  it("핀 번호와 구간 라벨을 렌더한다", () => {
    const items = [item("a", 37.54, 127.05, 8), item("b", 37.55, 127.06)];
    const { container, getByText } = render(<MapView items={items} />);
    // 핀 2개
    expect(container.querySelectorAll("circle").length).toBe(2);
    // 도보 라벨
    expect(getByText("도보 8분")).toBeDefined();
  });

  it("핀 클릭 시 onSelect가 인덱스와 함께 호출된다", () => {
    const onSelect = vi.fn();
    const items = [item("a", 37.54, 127.05)];
    const { container } = render(<MapView items={items} onSelect={onSelect} />);
    const pinGroup = container.querySelector("g[style] circle")?.parentElement;
    pinGroup?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(onSelect).toHaveBeenCalledWith(0);
  });
});
