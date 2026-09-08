// 단일 상태(Single Source of Truth): 수동 조작과 AI 응답을 하나의 상태로 관리.
import { create } from "zustand";

import { api } from "@/services/api";
import { mapService } from "@/services/mapService";
import { toast } from "@/store/toastStore";
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
  connected: boolean; // 소켓 연결 상태 (5-4)
  notFound: boolean; // 코스 없음(404)
  history: string[][]; // 수동 편집 되돌리기 스택 (편집 직전 place_id 목록)
  setCourse: (course: Course) => void;
  setLocked: (locked: boolean) => void;
  setStage: (stage: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  appendMessage: (message: ChatMessage) => void;
  setConnected: (connected: boolean) => void;
  setNotFound: (notFound: boolean) => void;
  // 수동 편집: 드래그로 순서 변경 후 이동시간 재계산 (4-3). AI 호출 없음 → 무료.
  reorder: (from: number, to: number) => Promise<void>;
  remove: (index: number) => Promise<void>;
  addPlace: (placeId: string) => Promise<void>;
  undo: () => Promise<void>;
  canUndo: () => boolean;
}

async function recalcRoutes(items: TimelineItem[]): Promise<TimelineItem[]> {
  // 기존 구간에서 이동수단을 먼저 확보(원본 기준). 없으면 walk.
  const mode: TravelMode = items.find((it) => it.travel_to_next)?.travel_to_next?.mode ?? "walk";
  const next = items.map((it) => ({ ...it, travel_to_next: null as TimelineItem["travel_to_next"] }));
  // 구간 계산은 서로 독립 → 병렬 조회 후 배치
  const routes = await Promise.all(
    next.slice(0, -1).map((it, i) => mapService.getRoute(it.place, next[i + 1].place, mode)),
  );
  routes.forEach((r, i) => (next[i].travel_to_next = r));
  return next;
}

export const useCourseStore = create<CourseState>((set, get) => ({
  course: null,
  locked: false,
  stage: null,
  messages: [],
  connected: true,
  notFound: false,
  history: [],
  setCourse: (course) => set({ course, locked: course.locked, notFound: false }),
  setLocked: (locked) => set({ locked }),
  setStage: (stage) => set({ stage }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
  setConnected: (connected) => set({ connected }),
  setNotFound: (notFound) => set({ notFound }),

  // 수동 편집: 낙관적 로컬 갱신 후 서버 큐로 직렬화(무료). 서버 broadcast 가 최종 반영.
  reorder: async (from, to) => {
    const { course, locked } = get();
    if (!course || locked) return; // Lock 상태에서는 프론트단에서 즉시 차단
    const items = [...course.items];
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    pushHistory(get, set, course);
    await applyManualEdit(set, course, items);
  },

  remove: async (index) => {
    const { course, locked } = get();
    if (!course || locked) return;
    const items = course.items.filter((_, i) => i !== index);
    pushHistory(get, set, course);
    await applyManualEdit(set, course, items);
  },

  // 추천("함께 가요") 장소 추가: 서버가 동선 재계산 후 최종 상태 반환.
  addPlace: async (placeId) => {
    const { course, locked } = get();
    if (!course || locked) return;
    pushHistory(get, set, course);
    try {
      const updated = await api.addPlace(course.id, placeId);
      set({ course: updated });
    } catch {
      toast("장소를 추가하지 못했어요. 잠시 후 다시 시도해주세요.", "error");
    }
  },

  canUndo: () => get().history.length > 0,

  // 되돌리기: 편집 직전 place_id 목록을 서버에 통째로 설정(삭제된 장소도 복원됨).
  undo: async () => {
    const { course, locked, history } = get();
    if (!course || locked || history.length === 0) return;
    const prev = history[history.length - 1];
    set({ history: history.slice(0, -1) });
    try {
      const updated = await api.setItems(course.id, prev);
      set({ course: updated });
    } catch {
      toast("되돌리지 못했어요. 연결 상태를 확인해주세요.", "error");
    }
  },
}));

const HISTORY_MAX = 20;

function pushHistory(
  get: () => CourseState,
  set: (partial: Partial<CourseState>) => void,
  course: Course,
): void {
  const snapshot = course.items.map((it) => it.place.id);
  set({ history: [...get().history, snapshot].slice(-HISTORY_MAX) });
}

async function applyManualEdit(
  set: (partial: Partial<CourseState>) => void,
  course: Course,
  items: TimelineItem[],
): Promise<void> {
  const recalced = await recalcRoutes(items); // 낙관적 로컬 반영(즉각 UX)
  set({ course: { ...course, items: recalced } });
  try {
    // 서버 큐 경유로 영속화 + 참가자 broadcast. 실패해도 로컬 상태는 유지.
    await api.setItems(course.id, items.map((it) => it.place.id));
  } catch {
    toast("변경 사항을 저장하지 못했어요. 새로고침하면 이전 상태로 돌아갑니다.", "error");
  }
}
