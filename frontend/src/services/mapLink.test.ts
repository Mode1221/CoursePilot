import { describe, expect, it } from "vitest";

import { naverMapUrl } from "./mapLink";
import type { Place } from "@/types";

const place = { id: "p", name: "성수 카페", lat: 37.5, lng: 127.04 } as Place;

describe("naverMapUrl", () => {
  it("장소 이름을 인코딩해 검색 링크를 만든다", () => {
    expect(naverMapUrl(place)).toContain(encodeURIComponent("성수 카페"));
  });

  it("좌표를 함께 넘긴다", () => {
    const url = naverMapUrl(place);
    expect(url).toContain("lat=37.5");
    expect(url).toContain("lng=127.04");
  });
});
