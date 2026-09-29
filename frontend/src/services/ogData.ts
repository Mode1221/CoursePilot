// 미리보기(OG)용 서버 조회. SSR 은 컨테이너 내부 주소로 곧장 부른다(apiBase.ts `serverApiBase`).
// 미리보기 하나 때문에 페이지가 멈추면 안 된다 — 늦거나 실패하면 null(일반 카드로 간다).
import { serverApiBase } from "@/services/apiBase";
import type { TogetherPreview } from "@/services/ogText";
import type { Course } from "@/types";

export const OG_TIMEOUT_MS = 5_000;

async function getJson<T>(path: string, init: RequestInit & { next?: { revalidate: number } }): Promise<T | null> {
  try {
    const res = await fetch(`${serverApiBase()}${path}`, { ...init, signal: AbortSignal.timeout(OG_TIMEOUT_MS) });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null; // 백엔드 미가동·네트워크 실패·시간 초과
  }
}

/** 공유 코스(읽기 전용 화면과 같은 공개 조회). */
export function fetchCourse(id: string): Promise<Course | null> {
  return getJson<Course>(`/courses/${encodeURIComponent(id)}`, { next: { revalidate: 60 } });
}

/**
 * 같이 정하기 링크 미리보기. 열람 이벤트를 남기지 않는 전용 조회를 쓴다 —
 * 메신저 서버가 미리보기를 만들려고 링크를 가져가는 건 상대가 연 게 아니다.
 */
export function fetchTogetherPreview(token: string): Promise<TogetherPreview | null> {
  return getJson<TogetherPreview>(`/together/${encodeURIComponent(token)}/preview`, { cache: "no-store" });
}
