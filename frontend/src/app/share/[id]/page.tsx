"use client";

import { useEffect } from "react";

import MapPanel from "@/components/MapPanel";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";

// 공유 읽기 전용 뷰 (4-5). AI 대화 기록 없이 픽스된 최종 타임라인/지도만 열람.
export default function SharePage({ params }: { params: { id: string } }) {
  const setCourse = useCourseStore((s) => s.setCourse);

  useEffect(() => {
    api.getCourse(params.id).then(setCourse).catch(() => {});
  }, [params.id, setCourse]);

  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      <MapPanel readOnly />
    </div>
  );
}
