import type { ReactNode } from "react";

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
    <main
      style={{
        padding: "var(--sp-12) var(--sp-4)",
        maxWidth: 720,
        margin: "0 auto",
        lineHeight: 1.7,
      }}
    >
      <p
        role="note"
        style={{
          padding: "var(--sp-3)",
          border: "1px solid var(--border)",
          borderRadius: "var(--r-md)",
          background: "var(--surface)",
          fontSize: "var(--fs-sm)",
          marginBottom: "var(--sp-6)",
        }}
      >
        <strong>법률 검토 전 초안입니다.</strong> 정식 서비스 개시 전 변호사 검토를 거쳐
        확정합니다. 현재 내용은 참고용이며 그대로 효력을 갖지 않습니다.
      </p>
      <h1>{title}</h1>
      <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
        최종 개정일: {updatedOn}
      </p>
      {children}
      <p style={{ marginTop: "var(--sp-8)", fontSize: "var(--fs-sm)" }}>
        <a href="/">← 홈으로</a>
      </p>
    </main>
  );
}
