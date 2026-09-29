// 세션: 로그인 회원(카카오·전화) 또는 체험 계정(로그인 없이 1회). 둘 다 서버가 준 서명 토큰으로만 인정된다.
import { create } from "zustand";

const KEY = "coursepilot_user_id";
// 서명 토큰. id 만으로는 남의 계정이 되지 않도록 서버가 함께 내려 준다.
const TOKEN_KEY = "coursepilot_user_token";
// "guest" | "member" — 체험 중 안내를 보여줄지 정한다(권한 판단은 서버가 한다)
const KIND_KEY = "coursepilot_user_kind";

export type UserKind = "guest" | "member";

interface UserState {
  userId: string | null;
  kind: UserKind | null;
  questionsLeft: number | null;
  load: () => void;
  setUser: (userId: string, token?: string, kind?: UserKind) => void;
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

export function storedUserKind(): UserKind | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(KIND_KEY);
  return v === "guest" || v === "member" ? v : null;
}

export const useUserStore = create<UserState>((set) => ({
  userId: null,
  kind: null,
  questionsLeft: null,
  load: () => {
    if (typeof window === "undefined") return;
    const id = window.localStorage.getItem(KEY);
    // 예전 세션(종류 없음)은 전화 인증 회원이다
    if (id) set({ userId: id, kind: storedUserKind() ?? "member" });
  },
  setUser: (userId, token, kind = "member") => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(KEY, userId);
      // 토큰이 빈 값이면(개발 서버) 이전 토큰을 지워 혼선을 없앤다
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.setItem(KIND_KEY, kind);
    }
    set({ userId, kind });
  },
  clearUser: () => {
    // 회원 탈퇴 후 세션을 남기면 없는 계정으로 요청이 계속 나간다
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(KEY);
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(KIND_KEY);
    }
    set({ userId: null, kind: null, questionsLeft: null });
  },
  setQuestionsLeft: (n) => set({ questionsLeft: n }),
}));
