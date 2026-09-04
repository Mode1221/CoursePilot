import type { Course } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export const api = {
  async createCourse(): Promise<Course> {
    const res = await fetch(`${BASE}/courses`, { method: "POST" });
    if (!res.ok) throw new Error("createCourse failed");
    return res.json();
  },

  async getCourse(id: string): Promise<Course> {
    const res = await fetch(`${BASE}/courses/${id}`);
    if (!res.ok) throw new Error("getCourse failed");
    return res.json();
  },

  async generate(id: string, text: string, userId?: string): Promise<Course> {
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
