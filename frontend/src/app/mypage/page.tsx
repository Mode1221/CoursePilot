"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Card, EmptyState } from "@/components/ui";
import { api } from "@/services/api";
import { useUserStore } from "@/store/userStore";
import type { Course } from "@/types";

// 마이페이지: 내가 만든 코스 히스토리 + 북마크 (9-4).
export default function MyPage() {
  const { userId, load } = useUserStore();
  const [courses, setCourses] = useState<Course[]>([]);
  const [bookmarks, setBookmarks] = useState<Course[]>([]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!userId) return;
    api.myCourses(userId).then(setCourses).catch(() => {});
    api.myBookmarks(userId).then(setBookmarks).catch(() => {});
  }, [userId]);

  if (!userId) {
    return (
      <main style={{ padding: "var(--sp-12) var(--sp-4)", maxWidth: 640, margin: "0 auto" }}>
        <EmptyState
          title="로그인이 필요해요"
          description="가입하면 만든 코스와 북마크를 저장할 수 있어요."
          action={
            <Link href="/onboarding" style={{ textDecoration: "none" }}>
              <Button variant="primary" style={{ marginTop: "var(--sp-4)" }}>가입 · 설정하기</Button>
            </Link>
          }
        />
      </main>
    );
  }

  return (
    <main style={{ padding: "var(--sp-8) var(--sp-4)", maxWidth: 640, margin: "0 auto" }}>
      <h1>마이페이지</h1>

      <section style={{ marginTop: "var(--sp-6)" }}>
        <h2>내 코스</h2>
        <CourseList items={courses} hrefBase="/plan" empty="아직 만든 코스가 없어요." />
      </section>

      <section style={{ marginTop: "var(--sp-8)" }}>
        <h2>북마크</h2>
        <CourseList items={bookmarks} hrefBase="/share" empty="북마크한 코스가 없어요." />
      </section>
    </main>
  );
}

function CourseList({ items, hrefBase, empty }: { items: Course[]; hrefBase: string; empty: string }) {
  if (items.length === 0) return <EmptyState title={empty} />;
  return (
    <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "var(--sp-2)" }}>
      {items.map((c) => (
        <li key={c.id}>
          <Link href={`${hrefBase}/${c.id}`} style={{ textDecoration: "none", color: "inherit" }}>
            <Card interactive style={{ padding: "var(--sp-3) var(--sp-4)" }}>
              <div style={{ fontWeight: 600 }}>{c.title}</div>
              <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
                {c.region ? `${c.region} · ` : ""}{c.items.length}곳
              </div>
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  );
}
