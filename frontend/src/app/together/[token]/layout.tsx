import type { Metadata } from "next";

import { fetchTogetherPreview } from "@/services/ogData";
import { SITE_NAME, inviteText } from "@/services/ogText";
import { requestOrigin } from "@/services/siteUrl";

// 상대에게 카톡으로 가는 링크 — 미리보기에 "○○님이 데이트 코스를 같이 정하자고 해요"가 떠야 연다.
// 이미지는 같은 폴더의 opengraph-image.tsx 가 그린다.
export async function generateMetadata({ params }: { params: Promise<{ token: string }> }): Promise<Metadata> {
  const { token } = await params;
  const { title, description } = inviteText(await fetchTogetherPreview(token));
  return {
    metadataBase: await requestOrigin(),
    title,
    description,
    // 초대 링크는 검색에 걸릴 이유가 없다(토큰을 가진 사람만 보는 화면)
    robots: { index: false, follow: false },
    openGraph: { title, description, type: "website", siteName: SITE_NAME, locale: "ko_KR" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default function TogetherLayout({ children }: { children: React.ReactNode }) {
  return children;
}
