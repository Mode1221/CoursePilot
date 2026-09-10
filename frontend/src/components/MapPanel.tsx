"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import MapCanvas from "@/components/MapCanvas";
import { Badge, Button, EmptyState } from "@/components/ui";
import { api } from "@/services/api";
import { courseStats, formatCost, formatDuration } from "@/services/courseStats";
import { naverMapUrl } from "@/services/mapLink";
import { courseToText } from "@/services/courseText";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { MODE_LABEL, type Place } from "@/types";

// 모달·검색 패널은 클릭해야 열린다 — 첫 로드에서는 내려받지 않는다
const PlaceDetailModal = dynamic(() => import("@/components/PlaceDetailModal"));
const PlaceSearchPanel = dynamic(() => import("@/components/PlaceSearchPanel"));

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
  const [reasons, setReasons] = useState<Record<string, string[]>>({});
  const editDisabled = readOnly || locked;
  const courseId = course?.id;
  const itemKey = course?.items.map((it) => it.place.id).join(",") ?? "";

  // 왜 이 장소가 들어갔는지: 코스가 바뀔 때마다 다시 계산해 받아온다
  useEffect(() => {
    if (!courseId || !itemKey) {
      setReasons({});
      return;
    }
    let cancelled = false;
    api
      .courseReasons(courseId)
      .then((r) => {
        if (!cancelled) setReasons(r.reasons);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [courseId, itemKey]);

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

      <ol aria-label="코스 타임라인" style={{ listStyle: "none", padding: 0 }}>
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
                {/* 상세를 열지 않아도 영업시간이 미확인이라는 걸 알 수 있어야 한다 */}
                {item.place.hours_unverified && (
                  <span title="영업시간을 확인하지 못했어요. 방문 전 확인해 주세요">
                    {" "}
                    ⚠ 시간 확인 필요
                  </span>
                )}
                {/* 손으로 넣은 자리는 지우지 않는 대신, 문 닫은 시간이면 알려 준다 */}
                {item.hours_conflict && (
                  <span
                    style={{ color: "var(--danger)" }}
                    title="이 시간에는 영업하지 않거나 브레이크 타임이에요"
                  >
                    {" "}
                    ⚠ 영업시간 밖
                  </span>
                )}
              </span>
            </div>
            <div
              style={{
                color: "var(--text-muted)",
                fontSize: "var(--fs-sm)",
                display: "flex",
                gap: "var(--sp-2)",
              }}
            >
              {item.place.category && <span>{item.place.category}</span>}
              {/* 장소별 1인 예상 비용: 어디서 돈이 나가는지 카드에서 바로 보이게 */}
              {formatCost(item.place.price ?? 0) && <span>{formatCost(item.place.price ?? 0)}</span>}
              {/* 공유받은 사람도 편집 버튼 없이 바로 길을 찾을 수 있게 항상 노출 */}
              <a
                href={naverMapUrl(item.place)}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                aria-label={`${item.place.name} 지도에서 보기`}
              >
                지도
              </a>
            </div>
            {(reasons[item.place.id]?.length ?? 0) > 0 && (
              <div
                style={{
                  color: "var(--text-muted)",
                  fontSize: "var(--fs-xs)",
                  marginTop: "var(--sp-1)",
                }}
              >
                {reasons[item.place.id].join(" · ")}
              </div>
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
  const { places, travelMin, totalMin, costPerPerson, costKnown, costEstimated } = courseStats(course);
  const parts = [`${places}곳`];
  if (totalMin > 0) parts.push(`총 ${formatDuration(totalMin)}`);
  if (travelMin > 0) parts.push(`이동 ${formatDuration(travelMin)}`);
  const cost = formatCost(costPerPerson);
  // 가격을 모르는 장소가 섞여 있으면 "이상"으로 과소평가임을 밝힌다
  if (cost) {
    const suffix = costKnown < places ? " 이상" : costEstimated ? " 예상" : "";
    parts.push(`1인 ${cost}${suffix}`);
  }
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
