import Link from "next/link";

const LINK = { color: "var(--text-muted)" };

/** 하단 공통 링크. 약관·개인정보처리방침은 어느 화면에서든 닿아야 한다. */
export default function SiteFooter() {
  return (
    <footer
      style={{ marginTop: "var(--sp-8)", fontSize: "var(--fs-sm)", color: "var(--text-faint)" }}
    >
      <Link href="/onboarding" style={LINK}>선호 설정</Link>
      {" · "}
      <Link href="/mypage" style={LINK}>내 코스</Link>
      {" · "}
      <Link href="/terms" style={LINK}>이용약관</Link>
      {" · "}
      <Link href="/privacy" style={LINK}>개인정보처리방침</Link>
    </footer>
  );
}
