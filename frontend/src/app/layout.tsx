import type { Metadata } from "next";
import type { ReactNode } from "react";

import ToastHost from "@/components/ToastHost";

import "./globals.css";

export const metadata: Metadata = {
  title: "CoursePilot — 둘이 같이 정하는 데이트 코스",
  description: "데이트 계획, 검색 말고 상대에게 먼저 물어보세요. 30초면 둘 다 괜찮은 코스가 나옵니다.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f7f5" },
    { media: "(prefers-color-scheme: dark)", color: "#141311" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
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
      </body>
    </html>
  );
}
