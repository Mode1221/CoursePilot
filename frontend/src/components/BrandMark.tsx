import Link from "next/link";

/**
 * 픽앤어스 로고. 두 원(시작한 사람 보라 · 상대 청록)이 겹친 자리만 불꽃색 —
 * "두 사람의 답이 하나가 된다"를 그대로 그린다. 제목(heading)이 아니다(첫 제목은 각 화면의 h1).
 */
export function LogoGlyph({ size = 26 }: { size?: number }) {
  return (
    <svg width={size * (30 / 22)} height={size} viewBox="0 0 30 22" aria-hidden="true" focusable="false">
      <circle cx="10" cy="11" r="9" style={{ fill: "var(--owner)" }} />
      <circle cx="20" cy="11" r="9" style={{ fill: "var(--partner)" }} />
      {/* 교집합(렌즈): 두 원의 교점 (15, 11±√56) 을 잇는 두 호 */}
      <path d="M15 3.517 A9 9 0 0 1 15 18.483 A9 9 0 0 1 15 3.517 Z" style={{ fill: "var(--spark)" }} />
    </svg>
  );
}

export default function BrandMark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="cp-logo" aria-label="픽앤어스 처음으로">
      <LogoGlyph size={22} />
      <span>픽앤어스</span>
    </Link>
  );
}
