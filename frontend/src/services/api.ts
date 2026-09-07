import type { Course } from "@/types";

export interface GenerateResponse {
  course: Course;
  relaxed: boolean;
  needs_confirmation: boolean;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown; // JSON 직렬화됨
  userId?: string; // 있으면 X-User-Id 헤더
}

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
    throw new ApiError(res.status, detail || `${path} failed`);
  }
  // 204/빈 응답 대비
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  createCourse: (userId?: string) =>
    request<Course>("/courses", { method: "POST", userId }),

  getCourse: (id: string) => request<Course>(`/courses/${id}`),

  generate: (id: string, text: string, userId?: string) =>
    request<GenerateResponse>(`/courses/${id}/generate`, { method: "POST", body: { text }, userId }),

  signup: (phone: string) =>
    request<{ user_id: string; credits_left: number }>("/signup", { method: "POST", body: { phone } }),

  reorder: (id: string, placeIds: string[]) =>
    request<Course>(`/courses/${id}/reorder`, { method: "POST", body: { place_ids: placeIds } }),

  messages: (id: string) =>
    request<{ role: "user" | "ai"; text: string }[]>(`/courses/${id}/messages`),

  reviewSummary: (placeId: string, placeName: string) =>
    request<{ summary: string; count: number }>("/reviews/summary", {
      method: "POST",
      body: { place_id: placeId, place_name: placeName },
    }),

  setPreferences: (userId: string, prefs: Record<string, unknown>) =>
    request<void>(`/users/${userId}/preferences`, { method: "PUT", body: prefs }),

  myCourses: (userId: string) => request<Course[]>(`/users/${userId}/courses`),

  myBookmarks: (userId: string) => request<Course[]>(`/users/${userId}/bookmarks`),

  addBookmark: (userId: string, courseId: string) =>
    request<void>(`/users/${userId}/bookmarks/${courseId}`, { method: "PUT" }),

  credits: (userId: string) =>
    request<{ questions_left: number }>(`/users/${userId}/credits`),

  ratePlace: (placeId: string, stars: number) =>
    request<{ ok: boolean; average: number | null }>(`/places/${placeId}/rating`, {
      method: "POST",
      body: { stars },
    }),

  feedback: (courseId: string, kind: string, detail = "") =>
    request<{ ok: boolean }>(`/courses/${courseId}/feedback`, {
      method: "POST",
      body: { kind, detail },
    }),

  complete: (courseId: string) =>
    request<{ ok: boolean; places: number }>(`/courses/${courseId}/complete`, {
      method: "POST",
    }),

  purchase: (userId: string, points: number) =>
    request<{ questions_left: number }>(`/users/${userId}/purchase`, {
      method: "POST",
      body: { points },
    }),
};
