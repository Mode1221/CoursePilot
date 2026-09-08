import { describe, expect, it } from "vitest";

import { TRANSIT_OVERHEAD_MIN, mapService } from "./mapService";

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

describe("이동수단", () => {
  it("대중교통은 대기·환승 시간이 더해진다", async () => {
    const a = { id: "a", name: "a", lat: 37.5, lng: 127.0 };
    const b = { id: "b", name: "b", lat: 37.51, lng: 127.0 };
    const walk = await mapService.getRoute(a, b, "walk");
    const transit = await mapService.getRoute(a, b, "transit");
    expect(transit.duration_min).toBe(
      Math.max(1, Math.round(transit.distance_m / 250)) + TRANSIT_OVERHEAD_MIN,
    );
    expect(walk.duration_min).toBeGreaterThan(0);
  });
});
