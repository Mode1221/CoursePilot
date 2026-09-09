import type { Course } from "@/types";

export interface GenerateResponse {
  course: Course;
  relaxed: boolean;
  needs_confirmation: boolean;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** 서버가 붙인 추적 id. 문의 시 이 값으로 로그를 찾을 수 있다. */
    public requestId?: string,
  ) {
    super(message);
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown; // JSON 직렬화됨
  userId?: string; // 있으면 X-User-Id 헤더
}

// detail 이 없거나 사람이 읽을 수 없는 형태일 때 쓰는 기본 문구
const DEFAULT_ERROR = "요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.";

// 모든 API 호출 공통 처리: BASE, JSON 헤더, X-User-Id, 에러→ApiError, 파싱.
async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.userId) headers["X-User-Id"] = opts.userId;

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().then((b) => b?.detail).catch(() => null);
    const requestId = res.headers.get("X-Request-Id") ?? undefined;
    // detail 은 화면에 그대로 노출된다. 서버 검증 오류(422)는 배열/객체로 오고,
    // detail 이 없으면 내부 경로가 보이므로 사람이 읽을 수 있는 문구만 쓴다.
    const message = typeof detail === "string" && detail.trim() ? detail : DEFAULT_ERROR;
    throw new ApiError(res.status, message, requestId);
  }
  // 204/빈 응답 대비
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  createCourse: (userId?: string) =>
    request<Course>("/courses", { method: "POST", userId }),

  getCourse: (id: string) => request<Course>(`/courses/${id}`),

  renameCourse: (id: string, title: string, userId?: string) =>
    request<Course>(`/courses/${id}`, { method: "PATCH", body: { title }, userId }),

  duplicateCourse: (id: string, userId?: string) =>
    request<Course>(`/courses/${id}/duplicate`, { method: "POST", userId }),

  deleteCourse: (id: string, userId?: string) =>
    request<{ ok: boolean }>(`/courses/${id}`, { method: "DELETE", userId }),

  generate: (id: string, text: string, userId?: string) =>
    request<GenerateResponse>(`/courses/${id}/generate`, { method: "POST", body: { text }, userId }),

  // 완화 동의 후 재시도(크레딧 미소모)
  relax: (id: string, userId?: string) =>
    request<GenerateResponse>(`/courses/${id}/relax`, { method: "POST", userId }),

  requestSmsCode: (phone: string) =>
    request<{ sent: boolean; dev_code: string | null }>("/auth/sms/request", {
      method: "POST",
      body: { phone },
    }),

  verifySmsCode: (phone: string, code: string) =>
    request<{ verified: boolean }>("/auth/sms/verify", {
      method: "POST",
      body: { phone, code },
    }),

  signup: (phone: string) =>
    request<{ user_id: string; credits_left: number }>("/signup", { method: "POST", body: { phone } }),

  reorder: (id: string, placeIds: string[]) =>
    request<Course>(`/courses/${id}/reorder`, { method: "POST", body: { place_ids: placeIds } }),

  setItems: (id: string, placeIds: string[]) =>
    request<Course>(`/courses/${id}/items`, { method: "POST", body: { place_ids: placeIds } }),

  searchPlaces: (region: string, q = "", limit = 8) =>
    request<import("@/types").Place[]>(
      `/places/search?region=${encodeURIComponent(region)}&q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  addPlace: (id: string, placeId: string) =>
    request<Course>(`/courses/${id}/places`, { method: "POST", body: { place_id: placeId } }),

  messages: (id: string) =>
    request<{ role: "user" | "ai"; text: string }[]>(`/courses/${id}/messages`),

  reviewSummary: (placeId: string, placeName: string) =>
    request<{ summary: string; count: number; pros: string[]; cons: string[] }>("/reviews/summary", {
      method: "POST",
      body: { place_id: placeId, place_name: placeName },
    }),

  courseReasons: (id: string) =>
    request<{ reasons: Record<string, string[]> }>(`/courses/${id}/reasons`),

  deleteAccount: (userId: string) =>
    request<{ ok: boolean; deleted_courses: number }>(`/users/${userId}`, {
      method: "DELETE",
      userId,
    }),

  getPreferences: (userId: string) =>
    request<{
      mood: string | null;
      budget: string | null;
      region: string | null;
      diet: string[];
      transport: string | null;
    }>(`/users/${userId}/preferences`, { userId }),

  setPreferences: (userId: string, prefs: Record<string, unknown>) =>
    request<void>(`/users/${userId}/preferences`, { method: "PUT", body: prefs, userId }),

  myCourses: (userId: string) => request<Course[]>(`/users/${userId}/courses`, { userId }),

  myBookmarks: (userId: string) => request<Course[]>(`/users/${userId}/bookmarks`, { userId }),

  addBookmark: (userId: string, courseId: string) =>
    request<void>(`/users/${userId}/bookmarks/${courseId}`, { method: "PUT", userId }),

  credits: (userId: string) =>
    request<{ questions_left: number }>(`/users/${userId}/credits`, { userId }),

  // 별점은 사람·장소당 한 표(다시 매기면 이전 점수 대체)라 사용자 id 를 함께 보낸다
  ratePlace: (placeId: string, stars: number, userId?: string) =>
    request<{ ok: boolean; average: number | null }>(`/places/${placeId}/rating`, {
      method: "POST",
      body: { stars },
      userId,
    }),

  relatedPlaces: (placeId: string) =>
    request<import("@/types").Place[]>(`/places/${placeId}/related`),

  // 재방문 의사는 사람·장소당 한 번만 신호로 세므로 사용자 id 를 함께 보낸다
  revisit: (placeId: string, userId?: string) =>
    request<{ ok: boolean; counted: boolean }>(`/places/${placeId}/revisit`, {
      method: "POST",
      userId,
    }),

  feedback: (courseId: string, kind: string, detail = "") =>
    request<{ ok: boolean }>(`/courses/${courseId}/feedback`, {
      method: "POST",
      body: { kind, detail },
    }),

  view: (courseId: string) =>
    request<{ ok: boolean }>(`/courses/${courseId}/view`, { method: "POST" }),

  satisfaction: (courseId: string, liked: boolean) =>
    request<{ ok: boolean }>(`/courses/${courseId}/satisfaction`, {
      method: "POST",
      body: { liked },
    }),

  complete: (courseId: string) =>
    request<{ ok: boolean; places: number }>(`/courses/${courseId}/complete`, {
      method: "POST",
    }),

  purchase: (userId: string, points: number) =>
    request<{ questions_left: number }>(`/users/${userId}/purchase`, {
      method: "POST",
      body: { points },
      userId,
    }),
};
