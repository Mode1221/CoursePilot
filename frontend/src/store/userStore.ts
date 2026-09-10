// 로그인(전화 인증) 회원 세션. 생성자만 AI 사용 가능(크레딧 책임 한정).
import { create } from "zustand";

const KEY = "coursepilot_user_id";
// 서명 토큰. id 만으로는 남의 계정이 되지 않도록 서버가 함께 내려 준다.
const TOKEN_KEY = "coursepilot_user_token";

interface UserState {
  userId: string | null;
  questionsLeft: number | null;
  load: () => void;
  setUser: (userId: string, token?: string) => void;
  clearUser: () => void;
  setQuestionsLeft: (n: number) => void;
}

/** 스토어 로드 전에도 저장된 세션 id 를 읽는다(첫 렌더 직후 클릭 대비). */
export function storedUserId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY);
}

/** 저장된 세션 토큰(없으면 null). API 호출 시 id 와 함께 보낸다. */
export function storedUserToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export const useUserStore = create<UserState>((set) => ({
  userId: null,
  questionsLeft: null,
  load: () => {
    if (typeof window === "undefined") return;
    const id = window.localStorage.getItem(KEY);
    if (id) set({ userId: id });
  },
  setUser: (userId, token) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(KEY, userId);
      // 토큰이 빈 값이면(개발 서버) 이전 토큰을 지워 혼선을 없앤다
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    }
    set({ userId });
  },
  clearUser: () => {
    // 회원 탈퇴 후 세션을 남기면 없는 계정으로 요청이 계속 나간다
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(KEY);
      window.localStorage.removeItem(TOKEN_KEY);
    }
    set({ userId: null, questionsLeft: null });
  },
  setQuestionsLeft: (n) => set({ questionsLeft: n }),
}));
