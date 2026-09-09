"use client";

import { useEffect, useState } from "react";

import MapPanel from "@/components/MapPanel";
import NotFound from "@/components/NotFound";
import { Button } from "@/components/ui";
import { api } from "@/services/api";
import { saveCalendar } from "@/services/calendar";
import { formatPlanDate } from "@/services/courseDate";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

// 공유 읽기 전용 뷰 (4-5). AI 대화 기록 없이 픽스된 최종 타임라인/지도만 열람.
// 메타데이터(OG)는 서버 컴포넌트인 app/share/[id]/page.tsx 가 담당한다.
export default function ShareView({ id }: { id: string }) {
  const setCourse = useCourseStore((s) => s.setCourse);
  const setNotFound = useCourseStore((s) => s.setNotFound);
  const notFound = useCourseStore((s) => s.notFound);
  const course = useCourseStore((s) => s.course);
  const { userId, load } = useUserStore();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // 다른 공유 링크로 이동하면 이전 응답이 늦게 와 남지 않도록 무시한다
    let cancelled = false;
    setNotFound(false);
    load();
    api
      .getCourse(id)
      .then((course) => {
        if (!cancelled) setCourse(course);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      });
    api.view(id).catch(() => {}); // 열람 신호(#5)
    return () => {
      cancelled = true;
    };
  }, [id, setCourse, setNotFound, load]);

  // 제목 아래 한 줄: 날짜 · 인원 · 지역 (있는 것만)
  const subtitle = [
    formatPlanDate(course?.plan_date),
    course?.party_size ? `${course.party_size}명` : null,
    course?.region,
  ]
    .filter(Boolean)
    .join(" · ");

  if (notFound) {
    return <NotFound message="공유 링크가 만료되었거나 삭제되었을 수 있어요." />;
  }

  async function bookmark() {
    if (!userId) return;
    try {
      await api.addBookmark(userId, id);
      setSaved(true);
      toast("북마크에 저장했어요.", "success");
    } catch {
      toast("북마크에 저장하지 못했어요.", "error");
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--sp-3) var(--sp-4)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <strong
            style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
          >
            {course?.title || "공유된 코스"}
          </strong>
          {subtitle && (
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{subtitle}</span>
          )}
        </span>
        <span style={{ display: "flex", gap: "var(--sp-2)" }}>
          <Button size="sm" onClick={() => saveCalendar(id)}>
            캘린더
          </Button>
          {userId && (
            <Button
              size="sm"
              variant={saved ? "secondary" : "primary"}
              onClick={bookmark}
              disabled={saved}
            >
              {saved ? "북마크됨" : "북마크"}
            </Button>
          )}
        </span>
      </header>
      <MapPanel readOnly />
    </div>
  );
}
