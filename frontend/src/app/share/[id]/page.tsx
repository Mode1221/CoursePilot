import type { Metadata } from "next";

import ShareView from "@/components/ShareView";
import { summarize } from "@/services/courseSummary";
import type { Course } from "@/types";

// 공유 링크는 메신저에 그대로 붙는다 → 서버에서 코스를 읽어 OG 미리보기를 채운다.
const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// 미리보기 하나 때문에 공유 페이지 렌더가 멈추면 안 된다 — 늦으면 기본 메타로 간다
const OG_TIMEOUT_MS = 5_000;

async function fetchCourse(id: string): Promise<Course | null> {
  try {
    const res = await fetch(`${API}/courses/${id}`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(OG_TIMEOUT_MS),
    });
    if (!res.ok) return null;
    return (await res.json()) as Course;
  } catch {
    return null; // 백엔드 미가동/네트워크 실패 시 기본 메타데이터로 폴백
  }
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const course = await fetchCourse(params.id);
  if (!course) {
    return { title: "공유된 코스 — CoursePilot" };
  }
  const title = `${course.title} — CoursePilot`;
  const description = summarize(course);
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      siteName: "CoursePilot",
    },
    twitter: { card: "summary", title, description },
  };
}

export default function SharePage({ params }: { params: { id: string } }) {
  return <ShareView id={params.id} />;
}
