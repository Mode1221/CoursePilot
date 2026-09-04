// 단일 상태(Single Source of Truth): 수동 조작과 AI 응답을 하나의 상태로 관리.
import { create } from "zustand";

import { api } from "@/services/api";
import { mapService } from "@/services/mapService";
import type { Course, TimelineItem, TravelMode } from "@/types";

export interface ChatMessage {
  role: "user" | "ai";
  text: string;
}

interface CourseState {
  course: Course | null;
  locked: boolean; // AI 처리 중 UI 편집 잠금 (5-3)
  stage: string | null; // AI 처리 단계 (5-4)
  messages: ChatMessage[]; // append-only 채팅 로그 (5-2)
  setCourse: (course: Course) => void;
  setLocked: (locked: boolean) => void;
  setStage: (stage: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  appendMessage: (message: ChatMessage) => void;
  // 수동 편집: 드래그로 순서 변경 후 이동시간 재계산 (4-3). AI 호출 없음 → 무료.
  reorder: (from: number, to: number) => Promise<void>;
  remove: (index: number) => Promise<void>;
}

async function recalcRoutes(items: TimelineItem[]): Promise<TimelineItem[]> {
  // 기존 구간에서 이동수단을 먼저 확보(원본 기준). 없으면 walk.
  const mode: TravelMode = items.find((it) => it.travel_to_next)?.travel_to_next?.mode ?? "walk";
  const next = items.map((it) => ({ ...it, travel_to_next: null as TimelineItem["travel_to_next"] }));
  for (let i = 0; i < next.length - 1; i++) {
    next[i].travel_to_next = await mapService.getRoute(next[i].place, next[i + 1].place, mode);
  }
  return next;
}

export const useCourseStore = create<CourseState>((set, get) => ({
  course: null,
  locked: false,
  stage: null,
  messages: [],
  setCourse: (course) => set({ course, locked: course.locked }),
  setLocked: (locked) => set({ locked }),
  setStage: (stage) => set({ stage }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),

  // 수동 편집: 낙관적 로컬 갱신 후 서버 큐로 직렬화(무료). 서버 broadcast 가 최종 반영.
  reorder: async (from, to) => {
    const { course, locked } = get();
    if (!course || locked) return; // Lock 상태에서는 프론트단에서 즉시 차단
    const items = [...course.items];
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    await applyManualEdit(get, set, course, items);
  },

  remove: async (index) => {
    const { course, locked } = get();
    if (!course || locked) return;
    const items = course.items.filter((_, i) => i !== index);
    await applyManualEdit(get, set, course, items);
  },
}));

async function applyManualEdit(
  get: () => CourseState,
  set: (partial: Partial<CourseState>) => void,
  course: Course,
  items: TimelineItem[],
): Promise<void> {
  const recalced = await recalcRoutes(items); // 낙관적 로컬 반영(즉각 UX)
  set({ course: { ...course, items: recalced } });
  try {
    // 서버 큐 경유로 영속화 + 참가자 broadcast. 실패해도 로컬 상태는 유지.
    await api.reorder(course.id, items.map((it) => it.place.id));
  } catch {
    /* 오프라인/테스트 환경: 로컬 반영만 유지 */
  }
}
