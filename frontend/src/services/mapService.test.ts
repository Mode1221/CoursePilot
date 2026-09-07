import { describe, expect, it } from "vitest";

import { mapService } from "./mapService";

describe("mapService (mock)", () => {
  it("searchPlaces가 요청 개수만큼 반환", async () => {
    const places = await mapService.searchPlaces("성수동", [], 5);
    expect(places).toHaveLength(5);
    expect(places[0].name).toContain("성수동");
  });

  it("getRoute가 이동시간/거리를 계산", async () => {
    const [a, b] = await mapService.searchPlaces("성수동", [], 2);
    const route = await mapService.getRoute(a, b, "walk");
    expect(route.duration_min).toBeGreaterThan(0);
    expect(route.mode).toBe("walk");
  });
});
