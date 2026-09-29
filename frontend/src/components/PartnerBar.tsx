"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Button } from "@/components/ui";
import { api } from "@/services/api";
import { readTogetherToken } from "@/services/togetherToken";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

/**
 * 링크로 들어온 상대(비가입)의 코스 화면 상단 바 — 수락, 내 카드 수정.
 * 교체·삭제·순서·AI 는 코스 화면의 원래 기능을 그대로 쓴다(토큰으로 허용).
 */
export default function PartnerBar({ courseId }: { courseId: string }) {
  const { userId } = useUserStore();
  const course = useCourseStore((s) => s.course);
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => setToken(readTogetherToken(courseId)), [courseId]);

  const t = course?.together;
  if (userId || !token || !t) return null; // 시작한 사람은 TogetherPanel 을 본다

  const accepted = t.accepted_by ?? [];
  const mine = accepted.includes(t.partner_name);

  async function accept() {
    try {
      const s = await api.togetherPartnerAccept(token!);
      toast(s.accepted_by.length >= 2 ? "둘 다 좋아요! 코스 확정 🎉" : "수락했어요.", "success");
    } catch {
      toast("수락하지 못했어요.", "error");
    }
  }

  return (
    <section
      style={{
        padding: "var(--sp-3) var(--sp-4)",
        borderRadius: "var(--r-lg)",
        background: "var(--surface)",
        boxShadow: "var(--shadow-1)",
        marginBottom: "var(--sp-3)",
        display: "flex",
        alignItems: "center",
        gap: "var(--sp-2)",
        flexWrap: "wrap",
      }}
    >
      <strong>{t.owner_name}님과 같이 정하는 중</strong>
      {t.stale && <Badge tone="warn">카드가 바뀌어 다시 합치는 중</Badge>}
      {accepted.length >= 2 ? (
        <Badge tone="brand">둘 다 좋아요 · 확정</Badge>
      ) : (
        <Button size="sm" variant="primary" onClick={accept} disabled={mine || !course?.items.length}>
          {mine ? "수락함 · 상대 기다리는 중" : "이 코스 좋아요"}
        </Button>
      )}
      <Link href={`/together/${token}?edit=1`} style={{ marginLeft: "auto" }}>
        <Button size="sm" variant="ghost">내 카드 수정</Button>
      </Link>
    </section>
  );
}
