"use client";

import { useCallback, useEffect, useState } from "react";

import MapView from "@/components/MapView";
import NaverMapView from "@/components/NaverMapView";
import { api } from "@/services/api";
import { type TimelineItem } from "@/types";

// 지도 렌더 선택: 네이버 지도 키 ID 가 있으면 실지도, 없으면 SVG 폴백.
// 키는 빌드에 박지 않고 런타임에 받는다(/config/public) — 키를 넣고 이미지를 다시 굽지 않아도 된다.
const BUILD_ID = process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID || "";
let runtimeId: Promise<string> | null = null;

function mapKeyId(): Promise<string> {
  if (BUILD_ID) return Promise.resolve(BUILD_ID);
  if (!runtimeId) {
    try {
      runtimeId = api
        .publicConfig()
        .then((c) => c?.naver_map_client_id || "")
        .catch(() => "");
    } catch {
      runtimeId = Promise.resolve(""); // 설정 조회 자체가 불가하면 SVG 폴백
    }
  }
  return runtimeId;
}

export default function MapCanvas({
  items,
  onSelect,
}: {
  items: TimelineItem[];
  onSelect?: (index: number) => void;
}) {
  const [keyId, setKeyId] = useState(BUILD_ID);
  const [sdkFailed, setSdkFailed] = useState(false);
  const onFail = useCallback(() => setSdkFailed(true), []);

  useEffect(() => {
    let alive = true;
    mapKeyId().then((id) => alive && setKeyId(id));
    return () => {
      alive = false;
    };
  }, []);

  if (keyId && !sdkFailed) {
    return <NaverMapView items={items} clientId={keyId} onSelect={onSelect} onFail={onFail} />;
  }
  return <MapView items={items} onSelect={onSelect} />;
}
