import type { Attribution } from "@/types";

/**
 * 반영 이유 칩 — 이 제품에서 색을 가장 세게 쓰는 유일한 자리.
 * 시작한 사람은 따뜻한 색, 상대는 시원한 색. 이름이 곧 색이라 "누가"가 먼저 읽힌다.
 * "👤지은 피곤해 → 이동 10분 이내"가 합의 코스의 아하 모먼트다.
 */
export default function AttributionChips({
  items,
  label = "반영된 의견",
  ownerName,
  size = "sm",
}: {
  items?: Attribution[];
  label?: string;
  /** 시작한 사람 이름 — 이 이름은 owner 색, 나머지는 partner 색 */
  ownerName?: string;
  size?: "sm" | "md";
}) {
  if (!items || items.length === 0) return null;
  return (
    <ul
      aria-label={label}
      style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexWrap: "wrap", gap: 6, maxWidth: "100%" }}
    >
      {items.map((a, i) => {
        const who = ownerName ? (a.who === ownerName ? "owner" : "partner") : i % 2 === 0 ? "owner" : "partner";
        const unmet = a.effect.includes("못 찾았어요");
        const yielded = a.effect.includes("양보");
        return (
          <li
            key={`${a.who}-${a.what}-${i}`}
            className={`cp-person cp-person--${who}`}
            style={{
              fontSize: size === "md" ? "var(--fs-md)" : "var(--fs-sm)",
              opacity: unmet || yielded ? 0.75 : 1,
              borderStyle: unmet ? "dashed" : undefined,
              border: unmet ? "1px dashed currentColor" : yielded ? "1px solid currentColor" : "1px solid transparent",
              background: unmet ? "transparent" : undefined,
            }}
          >
            <span className="cp-person__dot" aria-hidden="true" />
            <span style={{ whiteSpace: "nowrap" }}>
              <b style={{ fontWeight: 700 }}>{a.who}</b> <span style={{ opacity: 0.85 }}>{a.what}</span>
              <span aria-hidden="true" style={{ opacity: 0.5 }}> → </span>
            </span>
            <span style={{ minWidth: 0 }}>{unmet ? "맞는 곳 못 찾음 · 교체에서 골라요" : a.effect}</span>
          </li>
        );
      })}
    </ul>
  );
}
