import Link from "next/link";

import { LogoGlyph } from "@/components/BrandMark";

/** 하단 공통 링크. 약관·개인정보처리방침은 어느 화면에서든 닿아야 한다. */
export default function SiteFooter() {
  return (
    <footer className="cp-footer">
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <LogoGlyph size={16} />
        픽앤어스
      </span>
      <nav aria-label="하단 메뉴">
        <Link href="/onboarding">선호 설정</Link>
        <Link href="/mypage">내 코스</Link>
        <Link href="/terms">이용약관</Link>
        <Link href="/privacy">개인정보처리방침</Link>
      </nav>
    </footer>
  );
}
