import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import NaverMapView from "./NaverMapView";
import type { TimelineItem } from "@/types";

const items: TimelineItem[] = [
  { place: { id: "a", name: "a", lat: 37.5, lng: 127 }, travel_to_next: null },
];

describe("NaverMapView", () => {
  it("SDK 로드가 실패하면 onFail 로 알린다", async () => {
    const onFail = vi.fn();
    render(<NaverMapView items={items} clientId="test-id" onFail={onFail} />);

    // jsdom 은 스크립트를 실제로 받아오지 않으므로 오류 이벤트를 직접 발생시킨다
    const script = await waitFor(() => {
      const el = document.getElementById("naver-maps-sdk");
      if (!el) throw new Error("script not appended");
      return el;
    });
    script.dispatchEvent(new Event("error"));

    await waitFor(() => expect(onFail).toHaveBeenCalled());
  });
});
