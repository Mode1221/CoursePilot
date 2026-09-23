"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/services/api";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

/** 코스 화면 상단: 처음으로 · 내 코스 · 새 코스. 지금 코스에 갇히지 않게. */
export default function AppNav() {
  const { userId } = useUserStore();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function newCourse() {
    if (!userId) return router.push("/onboarding");
    setBusy(true);
    try {
      const course = await api.createCourse(userId);
      router.push(`/plan/${course.id}`);
    } catch {
      toast("새 코스를 만들지 못했어요.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <nav
      aria-label="주 메뉴"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--sp-3)",
        padding: "var(--sp-2) var(--sp-4)",
        borderBottom: "1px solid var(--border)",
        background: "var(--surface)",
      }}
    >
      <Link href="/" style={{ fontWeight: 700, color: "var(--text)", textDecoration: "none" }}>
        CoursePilot
      </Link>
      <Link href="/mypage" style={{ color: "var(--text-muted)", textDecoration: "none", fontSize: "var(--fs-sm)" }}>
        내 코스
      </Link>
      <Button size="sm" variant="secondary" onClick={newCourse} disabled={busy} style={{ marginLeft: "auto" }}>
        {userId ? "+ 새 코스" : "나도 만들어보기"}
      </Button>
    </nav>
  );
}
