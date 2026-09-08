"use client";

import { useState } from "react";

import MapCanvas from "@/components/MapCanvas";
import { Badge, Button, EmptyState } from "@/components/ui";
import PlaceDetailModal from "@/components/PlaceDetailModal";
import PlaceSearchPanel from "@/components/PlaceSearchPanel";
import { courseStats, formatCost, formatDuration } from "@/services/courseStats";
import { courseToText } from "@/services/courseText";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { MODE_LABEL, type Place } from "@/types";

// 시각화 패널: 지도(SVG 렌더) + 타임라인. 실제 지도 SDK 는 mapService 어댑터로 교체 예정.
export default function MapPanel({ readOnly = false }: { readOnly?: boolean }) {
  const course = useCourseStore((s) => s.course);
  const locked = useCourseStore((s) => s.locked);
  const reorder = useCourseStore((s) => s.reorder);
  const remove = useCourseStore((s) => s.remove);
  const undo = useCourseStore((s) => s.undo);
  const historyLen = useCourseStore((s) => s.history.length);
  const [selected, setSelected] = useState<Place | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [replaceIndex, setReplaceIndex] = useState<number | null>(null);
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
        {course.items.length > 0 && <CourseSummary course={course} />}
        {locked && <Badge tone="warn">잠금</Badge>}
        {course.items.length > 0 && (
          <Button
            size="sm"
            aria-label="코스 텍스트 복사"
            style={{ marginLeft: readOnly ? "auto" : undefined }}
            onClick={() => copyCourse(course)}
          >
            텍스트 복사
          </Button>
        )}
        {!readOnly && (
          <Button
            size="sm"
            aria-label="되돌리기"
            disabled={editDisabled || historyLen === 0}
            onClick={() => undo()}
          >
            ↩ 되돌리기
          </Button>
        )}
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
            {!readOnly && replaceIndex === i && (
              <div style={{ marginTop: "var(--sp-2)" }}>
                <PlaceSearchPanel
                  disabled={editDisabled}
                  replaceIndex={i}
                  onDone={() => setReplaceIndex(null)}
                />
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
                <Button
                  size="sm"
                  disabled={editDisabled}
                  onClick={() => setReplaceIndex(replaceIndex === i ? null : i)}
                >
                  교체
                </Button>
                <Button size="sm" variant="danger" disabled={editDisabled} onClick={() => remove(i)}>
                  삭제
                </Button>
              </div>
            )}
          </li>
        ))}
      </ol>

      {!readOnly && (
        <div style={{ marginTop: "var(--sp-3)" }}>
          <PlaceSearchPanel disabled={editDisabled} />
        </div>
      )}

      {selected && (
        <PlaceDetailModal place={selected} onClose={() => setSelected(null)} editable={!editDisabled} />
      )}
    </div>
  );
}

/** 장소 수 · 총 소요시간 · 이동시간 한 줄 요약. */
function CourseSummary({ course }: { course: Parameters<typeof courseStats>[0] }) {
  const { places, travelMin, totalMin, costPerPerson, costKnown } = courseStats(course);
  const parts = [`${places}곳`];
  if (totalMin > 0) parts.push(`총 ${formatDuration(totalMin)}`);
  if (travelMin > 0) parts.push(`이동 ${formatDuration(travelMin)}`);
  const cost = formatCost(costPerPerson);
  // 가격을 모르는 장소가 섞여 있으면 "이상"으로 과소평가임을 밝힌다
  if (cost) parts.push(`1인 ${cost}${costKnown < places ? " 이상" : ""}`);
  return (
    <span style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>{parts.join(" · ")}</span>
  );
}

/** 코스를 메신저에 붙여넣을 수 있는 텍스트로 클립보드에 복사. */
async function copyCourse(course: Parameters<typeof courseToText>[0]): Promise<void> {
  const url = typeof window !== "undefined" ? `${window.location.origin}/share/${course.id}` : undefined;
  try {
    await navigator.clipboard.writeText(courseToText(course, url));
    toast("코스를 복사했어요. 채팅방에 붙여넣어 보세요.", "success");
  } catch {
    toast("복사하지 못했어요.", "error");
  }
}
