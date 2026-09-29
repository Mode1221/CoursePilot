import { clearAcquisition } from "@/services/acquisition";
import type { InviteReward, LoginResult } from "@/services/api";
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
  // 서버가 첫 출처를 이미 받았고, 초대 토큰은 한 번만 쓴다
  clearAcquisition();
  if (res.moved_courses) toast(`체험 때 만든 코스 ${res.moved_courses}개를 이 계정으로 옮겼어요.`, "success");
  if (res.invite_reward) toast(`초대 보상! ${rewardText(res.invite_reward)}`, "success");
}

/** "7일 동안 하루 코스 5개·AI 수정 20번 더" — 보상 안내 문구(값은 서버에서 온다). */
export function rewardText(r: InviteReward): string {
  const parts: string[] = [];
  if (r.extra.course) parts.push(`코스 ${r.extra.course}개`);
  if (r.extra.ai) parts.push(`AI 수정 ${r.extra.ai}번`);
  if (!parts.length) return `${r.days}일 동안 더 넉넉하게 쓸 수 있어요.`;
  return `${r.days}일 동안 하루 ${parts.join("·")} 더 쓸 수 있어요.`;
}

/** 초대 화면 안내: "처음 가입하면 두 사람 모두 7일 동안 하루 코스 5개씩 더". */
export function inviteOfferText(r: InviteReward): string {
  const course = r.extra.course;
  const what = course ? `하루 코스 ${course}개씩 더 만들 수 있어요` : "더 넉넉하게 쓸 수 있어요";
  return `처음 가입하면 두 사람 모두 ${r.days}일 동안 ${what}.`;
}
