"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
      <main style={{ padding: 48, maxWidth: 640, margin: "0 auto" }}>
        <p>로그인이 필요합니다. <Link href="/onboarding">가입/설정</Link></p>
      </main>
    );
  }

  return (
    <main style={{ padding: 48, maxWidth: 640, margin: "0 auto" }}>
      <h1>마이페이지</h1>

      <section>
        <h2>내 코스</h2>
        <CourseList items={courses} hrefBase="/plan" empty="아직 만든 코스가 없습니다." />
      </section>

      <section>
        <h2>북마크</h2>
        <CourseList items={bookmarks} hrefBase="/share" empty="북마크한 코스가 없습니다." />
      </section>
    </main>
  );
}

function CourseList({ items, hrefBase, empty }: { items: Course[]; hrefBase: string; empty: string }) {
  if (items.length === 0) return <p style={{ color: "#999" }}>{empty}</p>;
  return (
    <ul>
      {items.map((c) => (
        <li key={c.id}>
          <Link href={`${hrefBase}/${c.id}`}>
            {c.title} {c.region ? `· ${c.region}` : ""} ({c.items.length}곳)
          </Link>
        </li>
      ))}
    </ul>
  );
}
