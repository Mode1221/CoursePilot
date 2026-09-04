"use client";

import { useCourseStore } from "@/store/courseStore";

// 시각화 패널: 지도 + 타임라인. 지도 SDK 는 mapService 어댑터를 통해 추후 연결.
export default function MapPanel() {
  const course = useCourseStore((s) => s.course);
  const locked = useCourseStore((s) => s.locked);
  const reorder = useCourseStore((s) => s.reorder);
  const remove = useCourseStore((s) => s.remove);

  if (!course) return <div style={{ padding: 24 }}>불러오는 중…</div>;

  return (
    <div style={{ padding: 16 }}>
      {/* TODO: Naver/Google 지도 렌더링 (mapService 경유). 지금은 타임라인 리스트만. */}
      <div
        style={{
          height: 240,
          background: "#f2f4f7",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#999",
          marginBottom: 16,
        }}
      >
        지도 영역 (핀 · 동선 선분)
      </div>

      <h3>타임라인 {locked && <span style={{ color: "#c60" }}>(잠금)</span>}</h3>
      {course.items.length === 0 && <p style={{ color: "#999" }}>아직 코스가 없습니다.</p>}

      <ol style={{ listStyle: "none", padding: 0 }}>
        {course.items.map((item, i) => (
          <li key={item.place.id} style={{ border: "1px solid #eee", borderRadius: 8, padding: 12, marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <strong>
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
            <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
              <button disabled={locked || i === 0} onClick={() => reorder(i, i - 1)}>
                ↑
              </button>
              <button disabled={locked || i === course.items.length - 1} onClick={() => reorder(i, i + 1)}>
                ↓
              </button>
              <button disabled={locked} onClick={() => remove(i)}>
                삭제
              </button>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
