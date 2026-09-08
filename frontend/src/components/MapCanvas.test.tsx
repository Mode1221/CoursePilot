import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MapCanvas from "./MapCanvas";
import type { TimelineItem } from "@/types";

function item(id: string, lat: number, lng: number): TimelineItem {
  return { place: { id, name: id, lat, lng }, travel_to_next: null };
}

describe("MapCanvas", () => {
  it("네이버 클라이언트 ID 미설정 시 SVG 폴백 렌더", () => {
    // 테스트 환경엔 NEXT_PUBLIC_NAVER_MAP_CLIENT_ID 없음 → SVG(MapView) 사용
    const { container } = render(<MapCanvas items={[item("a", 37.5, 127.0)]} />);
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.querySelector("circle")).not.toBeNull();
  });
});
