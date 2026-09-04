"use client";

import { useState } from "react";

import MapView from "@/components/MapView";
import PlaceDetailModal from "@/components/PlaceDetailModal";
import { useCourseStore } from "@/store/courseStore";
import type { Place } from "@/types";

// 시각화 패널: 지도(SVG 렌더) + 타임라인. 실제 지도 SDK 는 mapService 어댑터로 교체 예정.
export default function MapPanel({ readOnly = false }: { readOnly?: boolean }) {
  const course = useCourseStore((s) => s.course);
  const locked = useCourseStore((s) => s.locked);
  const reorder = useCourseStore((s) => s.reorder);
  const remove = useCourseStore((s) => s.remove);
  const [selected, setSelected] = useState<Place | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const editDisabled = readOnly || locked;

  if (!course) return <div style={{ padding: 24 }}>불러오는 중…</div>;

  function onDrop(to: number) {
    if (dragIndex === null || dragIndex === to || editDisabled) return;
    reorder(dragIndex, to);
    setDragIndex(null);
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 16 }}>
        <MapView items={course.items} onSelect={(i) => setSelected(course.items[i].place)} />
      </div>

      <h3>타임라인 {locked && <span style={{ color: "#c60" }}>(잠금)</span>}</h3>
      {course.items.length === 0 && <p style={{ color: "#999" }}>아직 코스가 없습니다.</p>}

      <ol style={{ listStyle: "none", padding: 0 }}>
        {course.items.map((item, i) => (
          <li
            key={item.place.id}
            draggable={!editDisabled}
            onDragStart={() => setDragIndex(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(i)}
            style={{
              border: "1px solid #eee",
              borderRadius: 8,
              padding: 12,
              marginBottom: 8,
              cursor: editDisabled ? "default" : "grab",
              opacity: dragIndex === i ? 0.5 : 1,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <strong
                onClick={() => setSelected(item.place)}
                style={{ cursor: "pointer", textDecoration: "underline" }}
              >
                {i + 1}. {item.place.name}
              </strong>
              <span style={{ color: "#888" }}>
                {item.arrive?.slice(0, 5)}~{item.depart?.slice(0, 5)}
              </span>
            </div>
            {item.place.category && <div style={{ color: "#888", fontSize: 13 }}>{item.place.category}</div>}
            {item.travel_to_next && (
              <div style={{ color: "#3a7", fontSize: 13 }}>
                → 다음까지 {item.travel_to_next.duration_min}분 ({item.travel_to_next.mode})
              </div>
            )}
            {!readOnly && (
              <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
                <button disabled={editDisabled || i === 0} onClick={() => reorder(i, i - 1)}>
                  ↑
                </button>
                <button disabled={editDisabled || i === course.items.length - 1} onClick={() => reorder(i, i + 1)}>
                  ↓
                </button>
                <button disabled={editDisabled} onClick={() => remove(i)}>
                  삭제
                </button>
              </div>
            )}
          </li>
        ))}
      </ol>

      {selected && <PlaceDetailModal place={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
