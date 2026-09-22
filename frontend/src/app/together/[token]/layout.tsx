import type { Metadata } from "next";

import { serverApiBase } from "@/services/apiBase";

// 상대에게 카톡으로 가는 링크 — 미리보기에 "○○님이 같이 정하재요 · 30초 · 가입 없음"이 떠야 연다.
const OG_TIMEOUT_MS = 5_000;

export async function generateMetadata({ params }: { params: { token: string } }): Promise<Metadata> {
  const fallback: Metadata = {
    title: "같이 데이트 코스 정하기 — CoursePilot",
    description: "30초 카드에 답하면 둘 다 괜찮은 코스가 나와요. 가입 없음.",
  };
  try {
    const res = await fetch(`${serverApiBase()}/together/${params.token}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(OG_TIMEOUT_MS),
    });
    if (!res.ok) return fallback;
    const s = (await res.json()) as { owner_name: string; request_text: string };
    const title = `${s.owner_name}님이 같이 정하재요 · 30초 · 가입 없음`;
    const description = `${s.request_text} — 컨디션·땡기는 것·싫은 것만 탭하면 둘 다 괜찮은 코스가 나와요.`;
    return {
      title,
      description,
      openGraph: { title, description, type: "website", siteName: "CoursePilot" },
      twitter: { card: "summary", title, description },
    };
  } catch {
    return fallback;
  }
}

export default function TogetherLayout({ children }: { children: React.ReactNode }) {
  return children;
}
