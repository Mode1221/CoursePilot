"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/services/api";
import type { Place } from "@/types";

// 장소 상세 모달 (4-2). 리뷰 요약은 RAG(협찬 필터 후) 결과.
export default function PlaceDetailModal({ place, onClose }: { place: Place; onClose: () => void }) {
  const [summary, setSummary] = useState<string>("불러오는 중…");
  const [myStars, setMyStars] = useState<number | null>(null);
  const [revisit, setRevisit] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = `place-${place.id}`;

  useEffect(() => {
    api
      .reviewSummary(place.id, place.name)
      .then((r) => setSummary(r.summary))
      .catch(() => setSummary("리뷰를 불러오지 못했습니다."));
  }, [place.id, place.name]);

  useEffect(() => {
    closeRef.current?.focus(); // 열릴 때 포커스 이동
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab") {
        // 포커스 트랩: 모달 내부 포커스 순환
        const items = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, [tabindex]:not([tabindex="-1"])',
        );
        if (!items || items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

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
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: 12, padding: 24, width: 360, maxWidth: "90%" }}
      >
        <h3 id={titleId} style={{ marginTop: 0 }}>{place.name}</h3>
        {place.category && <div style={{ color: "#888" }}>{place.category}</div>}
        {place.address && <div style={{ color: "#888", fontSize: 13 }}>{place.address}</div>}
        {place.rating != null && <div>⭐ {place.rating.toFixed(1)}</div>}
        {place.price != null && <div style={{ fontSize: 13 }}>1인 약 {place.price.toLocaleString()}원</div>}
        {(place.open_time || place.close_time) && (
          <div style={{ fontSize: 13 }}>
            영업 {place.open_time?.slice(0, 5)}~{place.close_time?.slice(0, 5)}
          </div>
        )}
        <h4>리뷰 요약</h4>
        <p style={{ color: "#444", fontSize: 14 }}>{summary}</p>

        <h4>다녀왔다면 별점을 남겨주세요</h4>
        <div role="group" aria-label="별점" style={{ display: "flex", gap: 4 }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              aria-label={`${n}점`}
              onClick={() => {
                setMyStars(n);
                api.ratePlace(place.id, n).catch(() => {});
              }}
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                fontSize: 22,
                color: myStars != null && n <= myStars ? "#f5a623" : "#ccc",
              }}
            >
              ★
            </button>
          ))}
        </div>
        {myStars != null && <p style={{ color: "#3a7", fontSize: 13 }}>평가 감사합니다!</p>}

        <button
          aria-pressed={revisit}
          onClick={() => {
            if (revisit) return;
            setRevisit(true);
            api.revisit(place.id).catch(() => {});
          }}
          style={{ marginTop: 8, marginRight: 8 }}
        >
          {revisit ? "또 가고 싶은 곳 ✓" : "또 가고 싶어요"}
        </button>

        <button ref={closeRef} onClick={onClose} style={{ marginTop: 8 }}>
          닫기
        </button>
      </div>
    </div>
  );
}
