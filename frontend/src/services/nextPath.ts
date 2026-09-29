/**
 * 로그인·체험 시작 뒤 돌아갈 주소. 우리 사이트 안의 경로만 받는다 —
 * `//evil.com`·`https://…` 를 받으면 로그인 직후 남의 사이트로 보내는 통로가 된다.
 */
export function safeNext(raw: string | null | undefined, fallback = "/"): string {
  if (!raw) return fallback;
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  return raw;
}

/** "new" 는 "새 코스를 만들어 그 화면으로" 라는 뜻(랜딩·상단 버튼에서 온 경우). */
export const NEW_COURSE = "new";

export function readQuery(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}
