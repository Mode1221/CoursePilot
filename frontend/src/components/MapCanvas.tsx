"use client";

import MapView from "@/components/MapView";
import NaverMapView from "@/components/NaverMapView";
import { type TimelineItem } from "@/types";

// 지도 렌더 선택: 네이버 지도 클라이언트 ID가 있으면 실지도, 없으면 SVG 폴백.
const NAVER_ID = process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID || "";

export default function MapCanvas({
  items,
  onSelect,
}: {
  items: TimelineItem[];
  onSelect?: (index: number) => void;
}) {
  if (NAVER_ID) {
    return <NaverMapView items={items} clientId={NAVER_ID} onSelect={onSelect} />;
  }
  return <MapView items={items} onSelect={onSelect} />;
}
