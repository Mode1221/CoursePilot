"use client";

import { useState } from "react";

import CourseTitle from "@/components/CourseTitle";
import { Button } from "@/components/ui";
import { api } from "@/services/api";
import { saveCalendar } from "@/services/calendar";
import { shareService } from "@/services/shareService";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

/**
 * 코스 화면 맨 아래 고정 줄 — 제목 · 다녀왔어요 · 캘린더 · 공유.
 * AI 채팅은 떠 있는 버튼(AiChatFab)으로 분리했다(아래 붙어 있던 채팅은 높이가 낮아 쓰기 불편했다).
 */
export default function CourseActionBar({ courseId }: { courseId: string }) {
  const { userId } = useUserStore();
  const course = useCourseStore((s) => s.course);
  const setCourse = useCourseStore((s) => s.setCourse);
  const [askSatisfaction, setAskSatisfaction] = useState(false);
  const hasItems = (course?.items.length ?? 0) > 0;

  async function markCompleted() {
    const res = await api.complete(courseId).catch(() => null);
    if (!res) return toast("기록을 저장하지 못했어요.", "error");
    if (course) setCourse({ ...course, completed: true });
    setAskSatisfaction(true);
    toast(course?.together ? "다녀오셨군요! 장소마다 어땠는지 남겨 주세요." : "다녀오셨군요!", "success");
  }

  function rate(liked: boolean) {
    api.satisfaction(courseId, liked).catch(() => {});
    setAskSatisfaction(false);
    toast(liked ? "좋아요! 비슷한 코스를 더 추천할게요." : "아쉬웠군요. 다음엔 더 잘 맞춰볼게요.", "success");
  }

  return (
    <footer
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--sp-2)",
        padding: "var(--sp-2) var(--sp-4)",
        paddingBottom: "calc(var(--sp-2) + env(safe-area-inset-bottom, 0px))",
        borderTop: "1px solid var(--border)",
        background: "var(--surface)",
        flexWrap: "wrap",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <CourseTitle courseId={courseId} title={course?.title ?? "코스"} userId={userId} />
      </div>
      {askSatisfaction ? (
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>코스 전체는 만족하셨나요?</span>
          <Button size="sm" onClick={() => rate(true)} aria-label="만족">👍</Button>
          <Button size="sm" onClick={() => rate(false)} aria-label="불만족">👎</Button>
        </span>
      ) : (
        <span style={{ display: "flex", gap: "var(--sp-2)" }}>
          {hasItems && !course?.completed && <Button size="sm" onClick={markCompleted}>다녀왔어요</Button>}
          {hasItems && <Button size="sm" onClick={() => saveCalendar(courseId)}>캘린더</Button>}
          <Button
            size="sm"
            variant="primary"
            onClick={() => shareService.share(`${window.location.origin}/share/${courseId}`)}
          >
            공유
          </Button>
        </span>
      )}
    </footer>
  );
}
