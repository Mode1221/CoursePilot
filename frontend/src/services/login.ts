import type { LoginResult } from "@/services/api";
import { toast } from "@/store/toastStore";
import type { UserKind } from "@/store/userStore";

export const KAKAO_STATE_KEY = "coursepilot_kakao_state";
export const KAKAO_NEXT_KEY = "coursepilot_kakao_next";

/** 카카오 콘솔에 등록하는 Redirect URI 와 정확히 같아야 한다. */
export function kakaoRedirectUri(): string {
  return `${window.location.origin}/auth/kakao`;
}

/** 로그인 성공 뒤 공통 처리: 세션 저장 → 체험 코스를 옮겼다면 알림. */
export function finishLogin(
  res: LoginResult,
  setUser: (id: string, token?: string, kind?: UserKind) => void,
): void {
  setUser(res.user_id, res.token, "member");
  if (res.moved_courses) toast(`체험 때 만든 코스 ${res.moved_courses}개를 이 계정으로 옮겼어요.`, "success");
}
