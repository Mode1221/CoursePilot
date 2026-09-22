// 합의 코스 상대(비가입)의 링크 토큰을 기기에 남긴다 — 코스 화면에서 수락·카드 수정·AI 사용에 쓴다.
const KEY = "coursepilot_together_token";

export function saveTogetherToken(courseId: string, token: string): void {
  try {
    window.localStorage.setItem(`${KEY}:${courseId}`, token);
  } catch {
    /* storage 막힘 */
  }
}

export function readTogetherToken(courseId: string): string | null {
  try {
    return window.localStorage.getItem(`${KEY}:${courseId}`);
  } catch {
    return null;
  }
}
