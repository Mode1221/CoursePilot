import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DEFAULT_DESCRIPTION, DEFAULT_TITLE, SITE_NAME } from "@/services/ogText";
import { requestOrigin } from "@/services/siteUrl";

// 랜딩(/)의 기본 미리보기 카드. 이미지는 같은 폴더의 opengraph-image.tsx 가 그리고,
// 메신저가 가져갈 절대 주소는 요청 호스트로 만든다(도메인을 빌드에 박지 않는다 — siteUrl.ts).
// 라우트 그룹이라 주소는 그대로 / 이고, 이 카드는 랜딩에만 붙는다(다른 정적 화면은 정적으로 남는다).
export async function generateMetadata(): Promise<Metadata> {
  return {
    metadataBase: await requestOrigin(),
    openGraph: {
      type: "website",
      siteName: SITE_NAME,
      locale: "ko_KR",
      title: DEFAULT_TITLE,
      description: DEFAULT_DESCRIPTION,
    },
    twitter: { card: "summary_large_image", title: DEFAULT_TITLE, description: DEFAULT_DESCRIPTION },
  };
}

export default function HomeLayout({ children }: { children: ReactNode }) {
  return children;
}
