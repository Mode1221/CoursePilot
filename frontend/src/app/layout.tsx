import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "CoursePilot — 검증된 모임 동선 플래너",
  description: "자연어로 조건만 말하면 영업시간·이동시간까지 검증된 모임 코스를 만들어 드립니다.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f9d84",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
