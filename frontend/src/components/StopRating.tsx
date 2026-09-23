"use client";

import { useState } from "react";

import { api } from "@/services/api";
import { readTogetherToken } from "@/services/togetherToken";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

/**
 * 다녀온 뒤 각자 몰래 👍/👎 — 우리 기록이 된다(다음 코스에서 둘 다 좋았던 곳은 또 가자, 싫었던 곳은 빼기).
 * 상대 평가는 보이지 않는다.
 */
export default function StopRating({ courseId, placeId }: { courseId: string; placeId: string }) {
  const { userId } = useUserStore();
  const [mine, setMine] = useState<number>(0);

  async function send(v: number) {
    const next = mine === v ? 0 : v;
    try {
      const token = userId ? null : readTogetherToken(courseId);
      const res = userId
        ? await api.togetherOwnerRate(courseId, userId, { [placeId]: next })
        : token
          ? await api.togetherPartnerRate(token, { [placeId]: next })
          : null;
      if (!res) return;
      setMine(res.mine[placeId] ?? 0);
      if (next !== 0) toast("우리 기록에 남겼어요", "success");
    } catch {
      toast("기록하지 못했어요.", "error");
    }
  }

  const btn = (v: number, label: string, emoji: string) => (
    <button
      type="button"
      aria-pressed={mine === v}
      aria-label={label}
      onClick={() => send(v)}
      style={{
        minWidth: 44,
        minHeight: 36,
        borderRadius: "var(--r-full)",
        border: `1.5px solid ${mine === v ? "var(--brand)" : "var(--line)"}`,
        background: mine === v ? "var(--brand-weak)" : "var(--surface)",
        color: mine === v ? "var(--brand-strong)" : "var(--text)",
        cursor: "pointer",
        font: "inherit",
      }}
    >
      {emoji}
    </button>
  );
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
      <span style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)" }}>어땠어요? (상대에겐 안 보여요)</span>
      {btn(1, "좋았어요", "👍")}
      {btn(-1, "별로였어요", "👎")}
    </div>
  );
}
