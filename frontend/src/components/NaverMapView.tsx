"use client";

import { useEffect, useRef } from "react";

import { type TimelineItem } from "@/types";

// 네이버 지도 JS SDK 렌더러. NEXT_PUBLIC_NAVER_MAP_CLIENT_ID 있을 때만 사용.
// SDK 스크립트는 최초 1회만 로드하고 이후 재사용한다.
declare global {
  interface Window {
    naver?: NaverMaps;
    /** 네이버 지도 SDK 가 인증 실패(미등록 도메인·잘못된 키) 시 부르는 전역 콜백 */
    navermap_authFailure?: () => void;
  }
}

// 네이버 지도 SDK 최소 타입(런타임 로드). 정밀 타입 불필요 부분은 넓게 둔다.
type LatLng = object;
interface Overlay {
  setMap: (map: NaverMap | null) => void;
}
interface NaverMap {
  setCenter: (p: LatLng) => void;
  setZoom: (z: number) => void;
  fitBounds: (b: object, margin?: Record<string, number>) => void;
}
interface NaverMaps {
  maps: {
    LatLng: new (lat: number, lng: number) => LatLng;
    LatLngBounds: new (sw: LatLng, ne: LatLng) => object;
    Map: new (el: HTMLElement, opts: Record<string, unknown>) => NaverMap;
    Marker: new (opts: Record<string, unknown>) => Overlay;
    Polyline: new (opts: Record<string, unknown>) => Overlay;
    Event: { addListener: (target: object, type: string, cb: () => void) => void };
  };
}

const SDK_ID = "naver-maps-sdk";
let sdkPromise: Promise<void> | null = null;

function loadSdk(clientId: string): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.naver?.maps) return Promise.resolve();
  if (sdkPromise) return sdkPromise;
  sdkPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.id = SDK_ID;
    // 신규 NCP Maps 는 ncpKeyId 파라미터를 쓴다(구 ncpClientId 는 인증 오류).
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${clientId}`;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("naver maps sdk load failed"));
    document.head.appendChild(s);
  });
  return sdkPromise;
}

export default function NaverMapView({
  items,
  clientId,
  onSelect,
  onFail,
  height = 240,
}: {
  items: TimelineItem[];
  clientId: string;
  onSelect?: (index: number) => void;
  /** SDK 로드 실패 시 호출(상위에서 SVG 폴백으로 전환). */
  onFail?: () => void;
  height?: number | string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<NaverMap | null>(null);
  const overlaysRef = useRef<Overlay[]>([]);

  useEffect(() => {
    let cancelled = false;
    // 스크립트는 받아지는데 키가 틀리거나 도메인이 미등록이면 SDK 가 이 콜백만 부른다 → 폴백
    window.navermap_authFailure = () => {
      if (!cancelled) onFail?.();
    };
    loadSdk(clientId)
      .then(() => {
        if (cancelled || !ref.current || !window.naver?.maps) return;
        const naver = window.naver;
        // 이전 코스의 마커·선을 먼저 지운다 — 새 코스(빈 코스)로 옮겼는데 옛 동선이 남아 보이던 문제
        overlaysRef.current.forEach((o) => o.setMap(null));
        overlaysRef.current = [];
        const seoul = new naver.maps.LatLng(37.5563, 126.9236);
        if (!mapRef.current) {
          mapRef.current = new naver.maps.Map(ref.current, { center: seoul, zoom: 13 });
        }
        const map = mapRef.current;
        if (items.length === 0) {
          map.setCenter(seoul);
          map.setZoom(13);
          return;
        }
        const path: LatLng[] = [];
        items.forEach((it, i) => {
          const pos = new naver.maps.LatLng(it.place.lat, it.place.lng);
          path.push(pos);
          const marker = new naver.maps.Marker({
            position: pos,
            map,
            title: it.place.name,
            icon: {
              content: `<div style="background:#0f9d84;color:#fff;border-radius:50%;width:26px;height:26px;line-height:26px;text-align:center;font-weight:700;border:2px solid #fff">${i + 1}</div>`,
            },
          });
          if (onSelect) naver.maps.Event.addListener(marker, "click", () => onSelect(i));
          overlaysRef.current.push(marker);
        });
        if (path.length > 1) {
          overlaysRef.current.push(
            new naver.maps.Polyline({ map, path, strokeColor: "#0f9d84", strokeWeight: 4, strokeStyle: "shortdash" }),
          );
          const lats = items.map((it) => it.place.lat);
          const lngs = items.map((it) => it.place.lng);
          const sw = new naver.maps.LatLng(Math.min(...lats), Math.min(...lngs));
          const ne = new naver.maps.LatLng(Math.max(...lats), Math.max(...lngs));
          map.fitBounds(new naver.maps.LatLngBounds(sw, ne), { top: 40, right: 40, bottom: 40, left: 40 });
        } else {
          map.setCenter(path[0]);
          map.setZoom(15);
        }
      })
      .catch(() => {
        if (!cancelled) onFail?.(); // 키 오류·네트워크 차단 등: 빈 지도 대신 폴백
      });
    return () => {
      cancelled = true;
    };
  }, [items, clientId, onSelect, onFail]);

  return (
    <div
      ref={ref}
      style={{ width: "100%", height, borderRadius: 8, background: "var(--surface-2)" }}
      aria-label="코스 지도"
    />
  );
}
