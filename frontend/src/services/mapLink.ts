import type { Place } from "@/types";

/** 네이버 지도 검색 링크. 좌표가 있으면 위치까지 함께 넘긴다. */
export function naverMapUrl(place: Place): string {
  const query = encodeURIComponent(place.name);
  const hasCoords = Number.isFinite(place.lat) && Number.isFinite(place.lng);
  const coords = hasCoords ? `&lat=${place.lat}&lng=${place.lng}` : "";
  return `https://map.naver.com/p/search/${query}${coords ? `?${coords.slice(1)}` : ""}`;
}
