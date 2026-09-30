import Link from "next/link";

/**
 * 픽앤어스 로고. 시작한 사람(보라)과 상대(청록) 두 원이 겹친 자리만 "우리"(--us) 색 —
 * 두 사람의 답이 하나가 된다는 제품 이야기를 그대로 그린다.
 * 제목(heading)이 아니다: 각 화면의 첫 제목은 그 화면의 h1 이다.
 */
export function LogoGlyph({ size = 22 }: { size?: number }) {
  return (
    <svg width={Math.round((size * 30) / 22)} height={size} viewBox="0 0 30 22" aria-hidden="true" focusable="false">
      <circle cx="10" cy="11" r="9" style={{ fill: "var(--owner)" }} />
      <circle cx="20" cy="11" r="9" style={{ fill: "var(--partner)" }} />
      {/* 겹친 렌즈: 두 원의 교점 (15, 11±√56) 을 잇는 두 호 */}
      <path d="M15 3.517 A9 9 0 0 1 15 18.483 A9 9 0 0 1 15 3.517 Z" style={{ fill: "var(--us)" }} />
    </svg>
  );
}

export default function BrandMark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="cp-logo">
      <LogoGlyph />
      <span>픽앤어스</span>
    </Link>
  );
}
