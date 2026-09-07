// 로그인(전화 인증) 회원 세션. 생성자만 AI 사용 가능(크레딧 책임 한정).
import { create } from "zustand";

const KEY = "coursepilot_user_id";

interface UserState {
  userId: string | null;
  questionsLeft: number | null;
  load: () => void;
  setUser: (userId: string) => void;
  setQuestionsLeft: (n: number) => void;
}

export const useUserStore = create<UserState>((set) => ({
  userId: null,
  questionsLeft: null,
  load: () => {
    if (typeof window === "undefined") return;
    const id = window.localStorage.getItem(KEY);
    if (id) set({ userId: id });
  },
  setUser: (userId) => {
    if (typeof window !== "undefined") window.localStorage.setItem(KEY, userId);
    set({ userId });
  },
  setQuestionsLeft: (n) => set({ questionsLeft: n }),
}));
