"use client";

import { Button } from "@/components/ui";
import type { Place } from "@/types";

/**
 * 칸별 대안 — "교체"를 누르면 검색창 대신 바로 고를 수 있는 2~3곳.
 * 같은 성격·가까운 순(동선이 크게 안 바뀐다). 교체하면 원래 장소가 대안 목록으로 돌아와 되돌리기 쉽다.
 */
export default function AlternativesList({
  items,
  disabled,
  onPick,
  onSearch,
}: {
  items: Place[];
  disabled?: boolean;
  onPick: (place: Place) => void;
  onSearch: () => void;
}) {
  return (
    <div
      role="group"
      aria-label="대안"
      style={{
        marginTop: "var(--sp-2)",
        padding: "var(--sp-3)",
        borderRadius: "var(--r-md)",
        background: "var(--surface-2)",
        display: "grid",
        gap: "var(--sp-2)",
      }}
    >
      <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)", fontWeight: 600 }}>이 자리 대신</span>
      {items.map((p) => (
        <div key={p.id} style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, overflowWrap: "anywhere" }}>{p.name}</div>
            <div style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>
              {(p.category ?? "").split(">").slice(-1)[0]?.trim()}
              {p.hot_reasons?.[0] ? ` · 🔥 ${p.hot_reasons[0]}` : ""}
              {p.is_popup ? " · 진행 중" : ""}
            </div>
          </div>
          <Button size="sm" variant="soft" disabled={disabled} onClick={() => onPick(p)} aria-label={`${p.name}(으)로 바꾸기`}>
            이걸로
          </Button>
        </div>
      ))}
      <Button size="sm" variant="ghost" onClick={onSearch} style={{ justifySelf: "start" }}>
        직접 찾기
      </Button>
    </div>
  );
}
