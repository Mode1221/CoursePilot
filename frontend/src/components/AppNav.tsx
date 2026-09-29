"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui";
import { createCourseUrl } from "@/services/newCourse";
import { NEW_COURSE } from "@/services/nextPath";
import { useUserStore } from "@/store/userStore";

/** 코스 화면 상단: 처음으로 · 내 코스 · 새 코스. 지금 코스에 갇히지 않게. */
export default function AppNav() {
  const { userId, kind } = useUserStore();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function newCourse() {
    if (!userId) return router.push(`/start?next=${NEW_COURSE}`);
    setBusy(true);
    const url = await createCourseUrl();
    if (url) router.push(url);
    setBusy(false);
  }

  const loginHref =
    typeof window !== "undefined"
      ? `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`
      : "/login";

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
      {kind === "guest" && (
        <Link
          href={loginHref}
          style={{ marginLeft: "auto", fontSize: "var(--fs-sm)", color: "var(--text-muted)", textDecoration: "none" }}
        >
          체험 중 · <span style={{ color: "var(--brand-strong)", fontWeight: 600 }}>로그인</span>
        </Link>
      )}
      <Button
        size="sm"
        variant="primary"
        onClick={newCourse}
        disabled={busy}
        style={{ marginLeft: kind === "guest" ? undefined : "auto" }}
      >
        {userId ? "+ 새 코스" : "나도 만들어보기"}
      </Button>
    </nav>
  );
}
