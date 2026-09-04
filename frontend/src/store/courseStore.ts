// 단일 상태(Single Source of Truth): 수동 조작과 AI 응답을 하나의 상태로 관리.
import { create } from "zustand";

import { mapService } from "@/services/mapService";
import type { Course, TimelineItem } from "@/types";

interface CourseState {
  course: Course | null;
  locked: boolean; // AI 처리 중 UI 편집 잠금 (5-3)
  setCourse: (course: Course) => void;
  setLocked: (locked: boolean) => void;
  // 수동 편집: 드래그로 순서 변경 후 이동시간 재계산 (4-3). AI 호출 없음 → 무료.
  reorder: (from: number, to: number) => Promise<void>;
  remove: (index: number) => Promise<void>;
}

async function recalcRoutes(items: TimelineItem[]): Promise<TimelineItem[]> {
  const next = items.map((it) => ({ ...it, travel_to_next: null as TimelineItem["travel_to_next"] }));
  for (let i = 0; i < next.length - 1; i++) {
    const mode = next[i].travel_to_next?.mode ?? "walk";
    next[i].travel_to_next = await mapService.getRoute(next[i].place, next[i + 1].place, mode);
  }
  return next;
}

export const useCourseStore = create<CourseState>((set, get) => ({
  course: null,
  locked: false,
  setCourse: (course) => set({ course, locked: course.locked }),
  setLocked: (locked) => set({ locked }),

  reorder: async (from, to) => {
    const { course, locked } = get();
    if (!course || locked) return; // Lock 상태에서는 프론트단에서 즉시 차단
    const items = [...course.items];
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    const recalced = await recalcRoutes(items);
    set({ course: { ...course, items: recalced } });
  },

  remove: async (index) => {
    const { course, locked } = get();
    if (!course || locked) return;
    const items = course.items.filter((_, i) => i !== index);
    const recalced = await recalcRoutes(items);
    set({ course: { ...course, items: recalced } });
  },
}));
