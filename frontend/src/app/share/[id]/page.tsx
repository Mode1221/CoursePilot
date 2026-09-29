import type { Metadata } from "next";

import ShareView from "@/components/ShareView";
import { fetchCourse } from "@/services/ogData";
import { SITE_NAME, courseText } from "@/services/ogText";
import { requestOrigin } from "@/services/siteUrl";

// 공유 링크는 메신저에 그대로 붙는다 → 서버에서 코스를 읽어 OG 미리보기를 채운다.
// SSR 은 컨테이너 내부 주소로 곧장 부르고(ogData.ts), 늦거나 실패하면 기본 메타로 간다.
// 이미지는 같은 폴더의 opengraph-image.tsx 가 그린다.
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const course = await fetchCourse(id);
  // 코스를 못 읽으면(없는 id·서버 장애) 일반 문구와 일반 카드 — 무엇이 없는지 드러내지 않는다
  const { title, description } = courseText(course);
  return {
    metadataBase: await requestOrigin(),
    title,
    description,
    openGraph: { title, description, type: "article", siteName: SITE_NAME, locale: "ko_KR" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function SharePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ShareView id={id} />;
}
