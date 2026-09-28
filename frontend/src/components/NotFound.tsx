import Link from "next/link";

// 코스 없음(404) 공통 빈 상태.
export default function NotFound({ message }: { message: string }) {
  return (
    <main style={{ padding: "var(--sp-12) var(--sp-4)", maxWidth: 560, margin: "0 auto", textAlign: "center" }}>
      <h1>코스를 찾을 수 없어요</h1>
      <p style={{ color: "var(--text-muted)" }}>{message}</p>
      {/* 링크 안에 버튼을 넣으면 탭이 두 번 걸리고 스크린리더가 둘 다 읽는다 — 버튼 모양 링크 하나로 */}
      <Link
        href="/"
        className="cp-btn cp-btn--primary"
        style={{ display: "inline-block", padding: "12px 20px", borderRadius: "var(--r-full)", fontWeight: 600, textDecoration: "none" }}
      >
        새 코스 시작하기
      </Link>
    </main>
  );
}
