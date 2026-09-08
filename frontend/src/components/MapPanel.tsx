"use client";

import { useState } from "react";

import MapCanvas from "@/components/MapCanvas";
import { Badge, Button, EmptyState } from "@/components/ui";
import PlaceDetailModal from "@/components/PlaceDetailModal";
import { useCourseStore } from "@/store/courseStore";
import { MODE_LABEL, type Place } from "@/types";

// 시각화 패널: 지도(SVG 렌더) + 타임라인. 실제 지도 SDK 는 mapService 어댑터로 교체 예정.
export default function MapPanel({ readOnly = false }: { readOnly?: boolean }) {
  const course = useCourseStore((s) => s.course);
  const locked = useCourseStore((s) => s.locked);
  const reorder = useCourseStore((s) => s.reorder);
  const remove = useCourseStore((s) => s.remove);
  const [selected, setSelected] = useState<Place | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const editDisabled = readOnly || locked;

  if (!course) return <div style={{ padding: "var(--sp-6)", color: "var(--text-muted)" }}>불러오는 중…</div>;

  function onDrop(to: number) {
    if (dragIndex === null || dragIndex === to || editDisabled) return;
    reorder(dragIndex, to);
    setDragIndex(null);
  }

  return (
    <div style={{ padding: "var(--sp-4)" }}>
      <div style={{ marginBottom: "var(--sp-4)" }}>
        <MapCanvas items={course.items} onSelect={(i) => setSelected(course.items[i].place)} />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", marginBottom: "var(--sp-3)" }}>
        <h3 style={{ margin: 0 }}>타임라인</h3>
        {locked && <Badge tone="warn">잠금</Badge>}
      </div>
      {course.items.length === 0 && (
        <EmptyState
          title="아직 코스가 없어요"
          description="오른쪽 채팅에 조건을 입력하면 검증된 동선을 만들어 드려요."
        />
      )}

      <ol style={{ listStyle: "none", padding: 0 }}>
        {course.items.map((item, i) => (
          <li
            key={item.place.id}
            draggable={!editDisabled}
            onDragStart={() => setDragIndex(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(i)}
            className="cp-enter"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--r-lg)",
              boxShadow: "var(--shadow-1)",
              padding: "var(--sp-3)",
              marginBottom: "var(--sp-2)",
              cursor: editDisabled ? "default" : "grab",
              opacity: dragIndex === i ? 0.5 : 1,
              transition: "opacity var(--dur) var(--ease)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span
                role="button"
                tabIndex={0}
                onClick={() => setSelected(item.place)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelected(item.place);
                  }
                }}
                style={{ cursor: "pointer", fontWeight: 700, color: "var(--text)" }}
                aria-label={`${item.place.name} 상세 보기`}
              >
                {i + 1}. {item.place.name}
              </span>
              <span style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)", whiteSpace: "nowrap" }}>
                {item.arrive?.slice(0, 5)}~{item.depart?.slice(0, 5)}
              </span>
            </div>
            {item.place.category && (
              <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>{item.place.category}</div>
            )}
            {item.travel_to_next && (
              <div style={{ color: "var(--brand-strong)", fontSize: "var(--fs-sm)", marginTop: "var(--sp-1)" }}>
                → 다음까지 {item.travel_to_next.duration_min}분 ({MODE_LABEL[item.travel_to_next.mode]})
              </div>
            )}
            {!readOnly && (
              <div style={{ marginTop: "var(--sp-2)", display: "flex", gap: "var(--sp-2)" }}>
                <Button size="sm" aria-label="위로" disabled={editDisabled || i === 0} onClick={() => reorder(i, i - 1)}>
                  ↑
                </Button>
                <Button
                  size="sm"
                  aria-label="아래로"
                  disabled={editDisabled || i === course.items.length - 1}
                  onClick={() => reorder(i, i + 1)}
                >
                  ↓
                </Button>
                <Button size="sm" variant="danger" disabled={editDisabled} onClick={() => remove(i)}>
                  삭제
                </Button>
              </div>
            )}
          </li>
        ))}
      </ol>

      {selected && (
        <PlaceDetailModal place={selected} onClose={() => setSelected(null)} editable={!editDisabled} />
      )}
    </div>
  );
}
