"use client";

import { useEffect, useRef } from "react";

import { type TimelineItem } from "@/types";

// 네이버 지도 JS SDK 렌더러. NEXT_PUBLIC_NAVER_MAP_CLIENT_ID 있을 때만 사용.
// SDK 스크립트는 최초 1회만 로드하고 이후 재사용한다.
declare global {
  interface Window { naver?: NaverMaps }
}

// 네이버 지도 SDK 최소 타입(런타임 로드). 정밀 타입 불필요 부분은 넓게 둔다.
type LatLng = object;
interface NaverMaps {
  maps: {
    LatLng: new (lat: number, lng: number) => LatLng;
    Map: new (el: HTMLElement, opts: Record<string, unknown>) => object;
    Marker: new (opts: Record<string, unknown>) => object;
    Polyline: new (opts: Record<string, unknown>) => object;
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
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpClientId=${clientId}`;
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
}: {
  items: TimelineItem[];
  clientId: string;
  onSelect?: (index: number) => void;
  /** SDK 로드 실패 시 호출(상위에서 SVG 폴백으로 전환). */
  onFail?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    loadSdk(clientId)
      .then(() => {
        if (cancelled || !ref.current || !window.naver?.maps || items.length === 0) return;
        const naver = window.naver;
        const center = new naver.maps.LatLng(items[0].place.lat, items[0].place.lng);
        const map = new naver.maps.Map(ref.current, { center, zoom: 14 });
        const path: unknown[] = [];
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
        });
        if (path.length > 1) {
          new naver.maps.Polyline({ map, path, strokeColor: "#0f9d84", strokeWeight: 4, strokeStyle: "shortdash" });
        }
      })
      .catch(() => {
        if (!cancelled) onFail?.(); // 키 오류·네트워크 차단 등: 빈 지도 대신 폴백
      });
    return () => {
      cancelled = true;
    };
  }, [items, clientId, onSelect, onFail]);

  return <div ref={ref} style={{ width: "100%", height: 240, borderRadius: 8, background: "var(--surface-2)" }} aria-label="코스 지도" />;
}
