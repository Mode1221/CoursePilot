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
  const busy = st.level === "붐빔" || st.level === "약간 붐빔";
  return (
    <p
      role="status"
      style={{
        margin: "6px 0 0",
        fontSize: "var(--fs-sm)",
        color: busy ? "var(--warn)" : "var(--text-muted)",
        fontWeight: busy ? 600 : 400,
      }}
    >
      지금 {st.area}는 {st.level}
      {busy && st.calmer_hour ? ` · ${st.calmer_hour}쯤 한산해져요` : ""}
    </p>
  );
}
