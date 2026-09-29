/**
 * 로그인·체험 시작 뒤 돌아갈 주소. 우리 사이트 안의 경로만 받는다 —
 * `//evil.com`·`https://…` 를 받으면 로그인 직후 남의 사이트로 보내는 통로가 된다.
 */
export function safeNext(raw: string | null | undefined, fallback = "/"): string {
  if (!raw) return fallback;
  // 브라우저는 주소의 탭·줄바꿈을 지우고 \ 를 / 로 읽는다 — "/\t/evil.com" 이 "//evil.com" 이 된다
  if (!raw.startsWith("/") || /[\u0000-\u001f\\]/.test(raw)) return fallback;
  try {
    const base = "https://coursepilot.invalid";
    const url = new URL(raw, base);
    if (url.origin !== base) return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}

/** "new" 는 "새 코스를 만들어 그 화면으로" 라는 뜻(랜딩·상단 버튼에서 온 경우). */
export const NEW_COURSE = "new";

export function readQuery(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}
