"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button, Card, EmptyState } from "@/components/ui";
import { api } from "@/services/api";
import { courseStats, formatDuration } from "@/services/courseStats";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";
import type { Course } from "@/types";

// 마이페이지: 내가 만든 코스 히스토리 + 북마크 (9-4).
export default function MyPage() {
  const { userId, load } = useUserStore();
  const [courses, setCourses] = useState<Course[]>([]);
  const [bookmarks, setBookmarks] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [prefs, setPrefs] = useState<string[]>([]);

  useEffect(() => {
    load();
  }, [load]);

  const reload = useCallback(() => {
    if (!userId) return;
    setLoadError(false);
    Promise.all([api.myCourses(userId), api.myBookmarks(userId)])
      .then(([mine, saved]) => {
        setCourses(mine);
        setBookmarks(saved);
      })
      .catch(() => setLoadError(true)); // 빈 목록처럼 보이지 않게 오류를 노출
  }, [userId]);

  useEffect(reload, [reload]);

  // 저장된 선호가 코스 추천에 쓰인다는 걸 보이게 한다(빈 값은 표시하지 않음)
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    api
      .getPreferences(userId)
      .then((p) => {
        if (cancelled) return;
        setPrefs(
          [p.region, p.mood, p.transport, p.budget, ...(p.diet ?? [])].filter(
            (v): v is string => Boolean(v),
          ),
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
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

      {loadError && (
        <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--fs-sm)" }}>
          목록을 불러오지 못했어요.{" "}
          <Button size="sm" onClick={reload}>
            다시 시도
          </Button>
        </p>
      )}

      <section
        style={{
          marginTop: "var(--sp-6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--sp-3)",
        }}
      >
        <p style={{ margin: 0, fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          {prefs.length > 0 ? `내 취향: ${prefs.join(" · ")}` : "취향을 설정하면 추천이 정확해져요."}
        </p>
        <Link href="/onboarding" style={{ textDecoration: "none", flexShrink: 0 }}>
          <Button size="sm">취향 수정</Button>
        </Link>
      </section>

      <section style={{ marginTop: "var(--sp-6)" }}>
        <h2>내 코스</h2>
        <CourseList
          items={courses}
          hrefBase="/plan"
          empty="아직 만든 코스가 없어요."
          onRename={async (id, title) => {
            try {
              const updated = await api.renameCourse(id, title, userId);
              setCourses((cs) => cs.map((c) => (c.id === id ? updated : c)));
              toast("이름을 변경했어요.", "success");
            } catch {
              toast("이름을 변경하지 못했어요.", "error");
            }
          }}
          onDuplicate={async (id) => {
            try {
              const copy = await api.duplicateCourse(id, userId);
              setCourses((cs) => [copy, ...cs]);
              toast("코스를 복제했어요.", "success");
            } catch {
              toast("코스를 복제하지 못했어요.", "error");
            }
          }}
          onDelete={async (id) => {
            try {
              await api.deleteCourse(id, userId);
              setCourses((cs) => cs.filter((c) => c.id !== id));
              toast("코스를 삭제했어요.", "success");
            } catch {
              toast("코스를 삭제하지 못했어요.", "error");
            }
          }}
        />
      </section>

      <section style={{ marginTop: "var(--sp-8)" }}>
        <h2>북마크</h2>
        <CourseList items={bookmarks} hrefBase="/share" empty="북마크한 코스가 없어요." />
      </section>
    </main>
  );
}

function CourseList({
  items,
  hrefBase,
  empty,
  onDelete,
  onRename,
  onDuplicate,
}: {
  items: Course[];
  hrefBase: string;
  empty: string;
  onDelete?: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onDuplicate?: (id: string) => void;
}) {
  if (items.length === 0) return <EmptyState title={empty} />;
  return (
    <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "var(--sp-2)" }}>
      {items.map((c) => (
        <li key={c.id} style={{ display: "flex", alignItems: "stretch", gap: "var(--sp-2)" }}>
          <Link
            href={`${hrefBase}/${c.id}`}
            style={{ flex: 1, minWidth: 0, textDecoration: "none", color: "inherit" }}
          >
            <Card interactive style={{ padding: "var(--sp-3) var(--sp-4)" }}>
              <div style={{ fontWeight: 600 }}>{c.title}</div>
              <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
                {summaryLine(c)}
              </div>
            </Card>
          </Link>
          {onRename && (
            <Button
              size="sm"
              aria-label={`${c.title} 이름 변경`}
              onClick={() => {
                const next = prompt("새 코스 이름", c.title)?.trim();
                if (next && next !== c.title) onRename(c.id, next);
              }}
            >
              이름
            </Button>
          )}
          {onDuplicate && (
            <Button
              size="sm"
              aria-label={`${c.title} 복제`}
              onClick={() => onDuplicate(c.id)}
            >
              복제
            </Button>
          )}
          {onDelete && (
            <Button
              variant="danger"
              size="sm"
              aria-label={`${c.title} 삭제`}
              onClick={() => {
                if (confirm(`"${c.title}" 코스를 삭제할까요?`)) onDelete(c.id);
              }}
            >
              삭제
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}

/** 카드 부제: "성수동 · 3곳 · 총 5시간" */
function summaryLine(course: Course): string {
  const { places, totalMin } = courseStats(course);
  const parts = [];
  if (course.region) parts.push(course.region);
  parts.push(`${places}곳`);
  if (totalMin > 0) parts.push(`총 ${formatDuration(totalMin)}`);
  return parts.join(" · ");
}
