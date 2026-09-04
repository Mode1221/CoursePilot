"use client";

import { useEffect, useState } from "react";

import { api } from "@/services/api";
import type { Place } from "@/types";

// 장소 상세 모달 (4-2). 리뷰 요약은 RAG(협찬 필터 후) 결과.
export default function PlaceDetailModal({ place, onClose }: { place: Place; onClose: () => void }) {
  const [summary, setSummary] = useState<string>("불러오는 중…");

  useEffect(() => {
    api
      .reviewSummary(place.id, place.name)
      .then((r) => setSummary(r.summary))
      .catch(() => setSummary("리뷰를 불러오지 못했습니다."));
  }, [place.id, place.name]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: 12, padding: 24, width: 360, maxWidth: "90%" }}
      >
        <h3 style={{ marginTop: 0 }}>{place.name}</h3>
        {place.category && <div style={{ color: "#888" }}>{place.category}</div>}
        {place.address && <div style={{ color: "#888", fontSize: 13 }}>{place.address}</div>}
        {place.rating != null && <div>⭐ {place.rating.toFixed(1)}</div>}
        {(place.open_time || place.close_time) && (
          <div style={{ fontSize: 13 }}>
            영업 {place.open_time?.slice(0, 5)}~{place.close_time?.slice(0, 5)}
          </div>
        )}
        <h4>리뷰 요약</h4>
        <p style={{ color: "#444", fontSize: 14 }}>{summary}</p>
        <button onClick={onClose} style={{ marginTop: 8 }}>
          닫기
        </button>
      </div>
    </div>
  );
}
