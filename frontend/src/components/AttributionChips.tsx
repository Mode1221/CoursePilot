import type { Attribution } from "@/types";

/** 반영 이유 칩 — "👤지은 피곤해 → 이동 10분 이내". 이 칩이 합의 코스의 아하 모먼트다. */
export default function AttributionChips({
  items,
  label = "반영된 의견",
}: {
  items?: Attribution[];
  label?: string;
}) {
  if (!items || items.length === 0) return null;
  return (
    <ul
      aria-label={label}
      style={{ listStyle: "none", padding: 0, margin: "var(--sp-2) 0 0", display: "flex", flexWrap: "wrap", gap: 6 }}
    >
      {items.map((a, i) => (
        <li
          key={`${a.who}-${a.what}-${i}`}
          style={{
            fontSize: "var(--fs-xs)",
            padding: "2px 8px",
            borderRadius: "var(--r-full)",
            background: "var(--brand-weak)",
            color: "var(--brand-strong)",
          }}
        >
          👤{a.who} {a.what === "예산" ? "예산" : a.what} → {a.effect}
        </li>
      ))}
    </ul>
  );
}
