// 전역 알림(토스트). 조용히 실패하던 경로들이 사용자에게 보이도록 한다.
import { create } from "zustand";

export type ToastTone = "info" | "error" | "success";

export interface Toast {
  id: number;
  text: string;
  tone: ToastTone;
}

interface ToastState {
  toasts: Toast[];
  push: (text: string, tone?: ToastTone) => number;
  dismiss: (id: number) => void;
}

let seq = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (text, tone = "info") => {
    const id = ++seq;
    set((s) => ({ toasts: [...s.toasts, { id, text, tone }].slice(-3) }));
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/** 스토어 밖(서비스 레이어)에서도 쓰는 단축 함수. */
export function toast(text: string, tone: ToastTone = "info"): void {
  useToastStore.getState().push(text, tone);
}
