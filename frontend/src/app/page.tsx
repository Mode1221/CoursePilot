"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/services/api";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function start() {
    setLoading(true);
    try {
      const course = await api.createCourse();
      router.push(`/plan/${course.id}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ padding: 48, maxWidth: 640, margin: "0 auto" }}>
      <h1>CoursePilot</h1>
      <p>자연어로 조건을 입력하면 물리적 제약이 검증된 모임 동선을 만들어 드립니다.</p>
      <button onClick={start} disabled={loading} style={{ padding: "12px 20px", fontSize: 16 }}>
        {loading ? "생성 중..." : "새 코스 시작"}
      </button>
    </main>
  );
}
