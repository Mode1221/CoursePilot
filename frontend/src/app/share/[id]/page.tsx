"use client";

import { useEffect, useState } from "react";

import MapPanel from "@/components/MapPanel";
import NotFound from "@/components/NotFound";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import { useUserStore } from "@/store/userStore";

// 공유 읽기 전용 뷰 (4-5). AI 대화 기록 없이 픽스된 최종 타임라인/지도만 열람.
export default function SharePage({ params }: { params: { id: string } }) {
  const setCourse = useCourseStore((s) => s.setCourse);
  const setNotFound = useCourseStore((s) => s.setNotFound);
  const notFound = useCourseStore((s) => s.notFound);
  const { userId, load } = useUserStore();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setNotFound(false);
    load();
    api.getCourse(params.id).then(setCourse).catch(() => setNotFound(true));
    api.view(params.id).catch(() => {}); // 열람 신호(#5)
  }, [params.id, setCourse, setNotFound, load]);

  if (notFound) {
    return <NotFound message="공유 링크가 만료되었거나 삭제되었을 수 있어요." />;
  }

  async function bookmark() {
    if (!userId) return;
    await api.addBookmark(userId, params.id).catch(() => {});
    setSaved(true);
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      {userId && (
        <div style={{ padding: 12, textAlign: "right" }}>
          <button onClick={bookmark} disabled={saved}>
            {saved ? "북마크됨" : "북마크"}
          </button>
        </div>
      )}
      <MapPanel readOnly />
    </div>
  );
}
