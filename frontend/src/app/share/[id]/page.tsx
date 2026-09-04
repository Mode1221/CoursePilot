"use client";

import { useEffect } from "react";

import { useState } from "react";

import MapPanel from "@/components/MapPanel";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import { useUserStore } from "@/store/userStore";

// 공유 읽기 전용 뷰 (4-5). AI 대화 기록 없이 픽스된 최종 타임라인/지도만 열람.
export default function SharePage({ params }: { params: { id: string } }) {
  const setCourse = useCourseStore((s) => s.setCourse);
  const { userId, load } = useUserStore();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    load();
    api.getCourse(params.id).then(setCourse).catch(() => {});
  }, [params.id, setCourse, load]);

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
