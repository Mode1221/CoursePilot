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

  async generate(id: string, text: string): Promise<Course> {
    const res = await fetch(`${BASE}/courses/${id}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error("generate failed");
    return res.json();
  },
};
