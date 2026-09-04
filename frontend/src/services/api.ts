import type { Course } from "@/types";

export interface GenerateResponse {
  course: Course;
  relaxed: boolean;
  needs_confirmation: boolean;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export const api = {
  async createCourse(userId?: string): Promise<Course> {
    const headers: Record<string, string> = {};
    if (userId) headers["X-User-Id"] = userId;
    const res = await fetch(`${BASE}/courses`, { method: "POST", headers });
    if (!res.ok) throw new Error("createCourse failed");
    return res.json();
  },

  async getCourse(id: string): Promise<Course> {
    const res = await fetch(`${BASE}/courses/${id}`);
    if (!res.ok) throw new Error("getCourse failed");
    return res.json();
  },

  async generate(id: string, text: string, userId?: string): Promise<GenerateResponse> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (userId) headers["X-User-Id"] = userId;
    const res = await fetch(`${BASE}/courses/${id}/generate`, {
      method: "POST",
      headers,
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || "generate failed");
    }
    return res.json();
  },

  async signup(phone: string): Promise<{ user_id: string; credits_left: number }> {
    const res = await fetch(`${BASE}/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    });
    if (!res.ok) throw new ApiError(res.status, "signup failed");
    return res.json();
  },

  async messages(id: string): Promise<{ role: "user" | "ai"; text: string }[]> {
    const res = await fetch(`${BASE}/courses/${id}/messages`);
    if (!res.ok) throw new ApiError(res.status, "messages failed");
    return res.json();
  },

  async reviewSummary(placeId: string, placeName: string): Promise<{ summary: string; count: number }> {
    const res = await fetch(`${BASE}/reviews/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ place_id: placeId, place_name: placeName }),
    });
    if (!res.ok) throw new ApiError(res.status, "reviewSummary failed");
    return res.json();
  },

  async setPreferences(userId: string, prefs: Record<string, unknown>): Promise<void> {
    const res = await fetch(`${BASE}/users/${userId}/preferences`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
    if (!res.ok) throw new ApiError(res.status, "setPreferences failed");
  },

  async myCourses(userId: string): Promise<Course[]> {
    const res = await fetch(`${BASE}/users/${userId}/courses`);
    if (!res.ok) throw new ApiError(res.status, "myCourses failed");
    return res.json();
  },

  async myBookmarks(userId: string): Promise<Course[]> {
    const res = await fetch(`${BASE}/users/${userId}/bookmarks`);
    if (!res.ok) throw new ApiError(res.status, "myBookmarks failed");
    return res.json();
  },

  async addBookmark(userId: string, courseId: string): Promise<void> {
    const res = await fetch(`${BASE}/users/${userId}/bookmarks/${courseId}`, { method: "PUT" });
    if (!res.ok) throw new ApiError(res.status, "addBookmark failed");
  },

  async credits(userId: string): Promise<{ questions_left: number }> {
    const res = await fetch(`${BASE}/users/${userId}/credits`);
    if (!res.ok) throw new ApiError(res.status, "credits failed");
    return res.json();
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}
