import Link from "next/link";
import type { ReactNode } from "react";

import BrandMark from "@/components/BrandMark";

/** 법률 문서 공통 껍데기. 본문은 페이지가 넘긴다. */
export default function LegalPage({
  title,
  updatedOn,
  children,
}: {
  title: string;
  updatedOn: string;
  children: ReactNode;
}) {
  return (
    <main className="cp-page cp-page--wide" style={{ lineHeight: 1.7 }}>
      <BrandMark />
      <p role="note" className="cp-note" style={{ marginTop: "var(--sp-6)", marginBottom: "var(--sp-6)" }}>
        <strong>베타 기간에 적용되는 내용입니다.</strong> 정식 서비스 개시 전 전문가 검토를 거쳐 바뀔 수 있으며,
        바뀌면 적용 전에 미리 알려 드립니다.
      </p>
      <h1 className="cp-page__title">{title}</h1>
      <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
        최종 개정일: {updatedOn}
      </p>
      {children}
      <p style={{ marginTop: "var(--sp-8)", fontSize: "var(--fs-sm)" }}>
        <Link href="/">← 홈으로</Link>
      </p>
    </main>
  );
}
