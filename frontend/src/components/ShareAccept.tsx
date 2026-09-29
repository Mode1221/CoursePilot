"use client";

import { useEffect, useState } from "react";

import { Badge, Button } from "@/components/ui";
import { api } from "@/services/api";
import { toast } from "@/store/toastStore";
import type { Course } from "@/types";

const TOKEN_KEY = "coursepilot_together_token";

/**
 * 공유 화면의 "둘 다 좋아요" — 상대(비가입)는 자기 링크 토큰으로 수락한다.
 * 토큰은 /together/[token] 을 열었을 때 기기에 남겨 둔다(가입 없이 이어지도록).
 */
export default function ShareAccept({ course }: { course: Course }) {
  const t = course.together!;
  const [token, setToken] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string[]>(t.accepted_by ?? []);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(`${TOKEN_KEY}:${course.id}`);
      if (saved) setToken(saved);
    } catch {
      /* storage 막힘 */
    }
  }, [course.id]);

  useEffect(() => setAccepted(t.accepted_by ?? []), [t.accepted_by]);

  const done = accepted.length >= 2;
  const mine = accepted.includes(t.partner_name);

  async function accept() {
    if (!token) return;
    try {
      const s = await api.togetherPartnerAccept(token);
      setAccepted(s.accepted_by);
      toast(s.accepted_by.length >= 2 ? "둘 다 좋아요! 코스 확정 🎉" : "수락했어요.", "success");
    } catch {
      toast("수락하지 못했어요.", "error");
    }
  }

  return (
    <div style={{ padding: "var(--sp-3) var(--sp-4)", display: "flex", alignItems: "center", gap: "var(--sp-2)", flexWrap: "wrap" }}>
      <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
        {t.owner_name}·{t.partner_name}의 카드를 합친 코스예요. 칸마다 누구 의견이 들어갔는지 표시했어요.
      </span>
      {done ? (
        <Badge tone="brand">둘 다 좋아요 · 확정</Badge>
      ) : token ? (
        <Button size="sm" variant="primary" onClick={accept} disabled={mine}>
          {mine ? "수락함 · 상대 기다리는 중" : "이 코스 좋아요"}
        </Button>
      ) : null}
    </div>
  );
}
