"use client";

import type { TimelineItem } from "@/types";

// 벤더 무관 SVG 지도 렌더. 실제 Naver/Google 지도는 mapService 어댑터로 교체 예정이나,
// 키 없이도 핀·동선을 시각화하기 위한 기본 렌더러.
const W = 560;
const H = 300;
const PAD = 40;

export default function MapView({
  items,
  onSelect,
}: {
  items: TimelineItem[];
  onSelect?: (index: number) => void;
}) {
  const pts = project(items);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ display: "block", width: "100%", height: 240, background: "#e9eef3", borderRadius: 8 }}
      role="img"
      aria-label="코스 지도"
    >
      <defs>
        <pattern id="cp-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M40 0H0V40" fill="none" stroke="#dbe2ea" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width={W} height={H} fill="url(#cp-grid)" />

      {pts.length > 1 && (
        <polyline
          points={pts.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none"
          stroke="#0f9d84"
          strokeWidth={3}
          strokeDasharray="2 8"
          strokeLinecap="round"
        />
      )}

      {pts.map((p, i) => (
        <g key={items[i].place.id} style={{ cursor: "pointer" }} onClick={() => onSelect?.(i)}>
          <circle cx={p.x} cy={p.y} r={14} fill="#e0533a" stroke="#fff" strokeWidth={3} />
          <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize={13} fill="#fff" fontWeight={700}>
            {i + 1}
          </text>
        </g>
      ))}
    </svg>
  );
}

function project(items: TimelineItem[]): { x: number; y: number }[] {
  if (items.length === 0) return [];
  const lats = items.map((it) => it.place.lat);
  const lngs = items.map((it) => it.place.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const spanLat = maxLat - minLat || 1;
  const spanLng = maxLng - minLng || 1;

  return items.map((it) => ({
    x: PAD + ((it.place.lng - minLng) / spanLng) * (W - 2 * PAD),
    // 위도는 위쪽이 커지므로 y축 반전
    y: PAD + ((maxLat - it.place.lat) / spanLat) * (H - 2 * PAD),
  }));
}
