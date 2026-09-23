"use client";

import { useEffect, useState } from "react";

import { api } from "@/services/api";

type Status = { area: string; level: string | null; message: string | null; calmer_hour: string | null } | null;

/** 동네 혼잡도 한 줄(서울 실시간 도시데이터). 데이터가 없으면 아무것도 그리지 않는다. */
export default function AreaStatusLine({ region }: { region?: string | null }) {
  const [st, setSt] = useState<Status>(null);
  useEffect(() => {
    let alive = true;
    if (!region) return;
    try {
      api
        .areaStatus(region)
        .then((s) => alive && setSt(s))
        .catch(() => {});
    } catch {
      /* 테스트 목 등에서 없는 경우 */
    }
    return () => {
      alive = false;
    };
  }, [region]);
  if (!st?.level) return null;
  // "지금 홍대 관광특구는 보통"은 무슨 뜻인지 알기 어려웠다 → 우리 동네 이름 + 사람이 얼마나 많은지 + 할 수 있는 것
  const place = region ?? st.area;
  const WORDS: Record<string, { text: string; tone: "calm" | "busy" }> = {
    여유: { text: "한산한 편이에요", tone: "calm" },
    보통: { text: "평소만큼 사람이 있어요", tone: "calm" },
    "약간 붐빔": { text: "조금 붐벼요", tone: "busy" },
    붐빔: { text: "사람이 많아요", tone: "busy" },
  };
  const w = WORDS[st.level] ?? { text: st.level, tone: "calm" as const };
  const busy = w.tone === "busy";
  return (
    <p
      role="status"
      style={{
        margin: "6px 0 0",
        fontSize: "var(--fs-sm)",
        color: busy ? "var(--warn)" : "var(--text-muted)",
        fontWeight: busy ? 600 : 400,
      }}
      title={`서울시 실시간 도시데이터 · ${st.area}`}
    >
      👥 지금 {place} 일대는 {w.text}
      {busy && st.calmer_hour ? ` · ${st.calmer_hour}쯤 한산해져요` : ""}
      <span style={{ color: "var(--text-faint)", fontWeight: 400 }}> · 서울시 실시간 인구</span>
    </p>
  );
}
