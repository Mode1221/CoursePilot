import type { Metadata } from "next";
import { Gowun_Batang } from "next/font/google";
import type { ReactNode } from "react";

import AcquisitionCapture from "@/components/AcquisitionCapture";
import ToastHost from "@/components/ToastHost";
import { DEFAULT_DESCRIPTION, DEFAULT_TITLE, SITE_NAME } from "@/services/ogText";

import "./globals.css";

// 기본 제목·설명. 정적 페이지(약관·로그인 등)는 그대로 정적으로 굽는다 — 여기서 요청 헤더를 읽으면
// 모든 화면이 요청마다 렌더하는 동적 페이지로 바뀐다. 미리보기 이미지는 절대 주소가 필요해서
// 요청 호스트를 아는 곳(랜딩 (home)/layout.tsx, together/[token], share/[id])에서만 붙인다.
// 표제용 서체: 손편지 같은 바탕체(고운바탕). 본문은 Pretendard. next/font 가 빌드 때 받아 자체 호스팅한다.
const display = Gowun_Batang({ weight: ["700"], subsets: ["latin"], display: "swap", variable: "--font-gowun", preload: false });

export const metadata: Metadata = {
  title: DEFAULT_TITLE,
  description: DEFAULT_DESCRIPTION,
  applicationName: SITE_NAME,
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "ko_KR",
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
  },
  twitter: { card: "summary", title: DEFAULT_TITLE, description: DEFAULT_DESCRIPTION },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbf5ee" },
    { media: "(prefers-color-scheme: dark)", color: "#171114" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" className={display.variable}>
      <head>
        {/* Pretendard: 한글 UI 표준 서체. jsDelivr(허용 호스트)에서 가변 폰트 하나만 받는다 */}
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>
        {children}
        <ToastHost />
        <AcquisitionCapture />
      </body>
    </html>
  );
}
