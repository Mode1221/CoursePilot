// 지도/장소 API 어댑터 레이어.
// 컨벤션: 컴포넌트는 벤더 SDK를 직접 호출하지 않고 이 인터페이스만 사용한다.
// 초기 구현체는 Naver 기준이나, 미설정 시 개발용 Mock 으로 폴백한다.

import type { Place, Route, TravelMode } from "@/types";

export interface MapService {
  searchPlaces(region: string, keywords: string[], limit?: number): Promise<Place[]>;
  getRoute(origin: Place, dest: Place, mode: TravelMode): Promise<Route>;
}

export const TRANSIT_OVERHEAD_MIN = 7; // 정류장 접근·대기·환승 (backend/app/constants.py 와 동일)
export const WALK_SWITCH_MIN = 20; // 이보다 먼 도보 구간은 대중교통으로 (backend/app/pipeline/validation.py)

/** 서버와 같은 규칙: 너무 먼 도보 구간은 대중교통으로 대체한다. */
export async function bestRoute(
  origin: Place,
  dest: Place,
  mode: TravelMode,
): Promise<Route> {
  const route = await mapService.getRoute(origin, dest, mode);
  if (mode !== "walk" || route.duration_min <= WALK_SWITCH_MIN) return route;
  const alt = await mapService.getRoute(origin, dest, "transit");
  return alt.duration_min < route.duration_min ? alt : route;
}

class MockMapService implements MapService {
  async searchPlaces(region: string, _keywords: string[], limit = 10): Promise<Place[]> {
    return Array.from({ length: limit }, (_, i) => ({
      id: `mock-${region}-${i}`,
      name: `${region} 장소 ${i + 1}`,
      category: i % 2 ? "cafe" : "restaurant",
      lat: 37.5445 + i * 0.001,
      lng: 127.0557 + i * 0.001,
      rating: 4.0 + (i % 5) * 0.1,
    }));
  }

  // 백엔드와 같은 규칙: 대중교통은 대기·환승 고정 비용을 더한다
  async getRoute(origin: Place, dest: Place, mode: TravelMode): Promise<Route> {
    const distance_m = Math.round(
      (Math.abs(origin.lat - dest.lat) + Math.abs(origin.lng - dest.lng)) * 111_000,
    );
    const speed = { walk: 67, car: 500, transit: 250 }[mode];
    return {
      from_place_id: origin.id,
      to_place_id: dest.id,
      mode,
      duration_min:
        Math.max(1, Math.round(distance_m / speed)) + (mode === "transit" ? TRANSIT_OVERHEAD_MIN : 0),
      distance_m,
    };
  }
}

// TODO: NaverMapService 구현 후 환경변수로 스위칭
export const mapService: MapService = new MockMapService();
