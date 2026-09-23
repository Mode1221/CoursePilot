import type { Attribution } from "@/types";

/**
 * 반영 칩 — "누가 무엇을 원해서 코스가 이렇게 됐는지".
 * 결과를 앞에, 이유는 흐리게: "시끄러운 곳 빼기" / "이동 12분 이내 · 많이 걷기" / "한식 · 민수 취향".
 * 사람은 앞의 이니셜 동그라미 색으로만 구분(시작한 사람 보라, 상대 청록 — 지도에 없는 색).
 * 전체 문장("민수 많이 걷기 → 이동 12분 이내로")은 aria-label 로 남겨 화면 낭독기·테스트가 읽는다.
 */
export function chipText(a: Attribution): { main: string; why: string | null; kind: "normal" | "unmet" | "yielded" } {
  const effect = a.effect.replace(/로$/, "");
  if (a.effect.includes("못 찾았어요")) return { main: `${a.what} 맞는 곳 못 찾음`, why: "교체에서 골라요", kind: "unmet" };
  if (a.effect.includes("양보")) return { main: `${a.what} 이번엔 양보`, why: "다음엔 먼저", kind: "yielded" };
  if (/칸$/.test(a.effect)) return { main: a.what, why: `${a.who} 취향`, kind: "normal" };
  if (effect.endsWith("빼기")) return { main: effect, why: null, kind: "normal" };
  const redundant = effect.includes(a.what) || a.what === "예산";
  return { main: effect, why: redundant ? null : a.what, kind: "normal" };
}

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
        const t = chipText(a);
        return (
          <li
            key={`${a.who}-${a.what}-${i}`}
            aria-label={`${a.who} ${a.what} → ${a.effect}`}
            className={`cp-person cp-person--${who}${t.kind === "unmet" ? " cp-person--unmet" : ""}`}
            style={{ fontSize: size === "md" ? "var(--fs-md)" : "var(--fs-sm)" }}
          >
            <span className="cp-person__avatar" aria-hidden="true" title={a.who}>
              {a.who.slice(0, 1)}
            </span>
            <span style={{ minWidth: 0 }}>
              {t.main}
              {t.why && <span className="cp-person__why"> · {t.why}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
