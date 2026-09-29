import { describe, expect, it } from "vitest";

import { inviteOfferText, rewardText } from "./login";

describe("초대 보상 문구", () => {
  const reward = { days: 7, extra: { course: 5, ai: 20, build: 5 } };

  it("초대 화면은 두 사람 모두 받는다는 걸 말한다", () => {
    expect(inviteOfferText(reward)).toBe("처음 가입하면 두 사람 모두 7일 동안 하루 코스 5개씩 더 만들 수 있어요.");
  });

  it("로그인 뒤 알림은 늘어난 몫을 말한다", () => {
    expect(rewardText(reward)).toBe("7일 동안 하루 코스 5개·AI 수정 20번 더 쓸 수 있어요.");
    expect(rewardText({ days: 3, extra: {} })).toBe("3일 동안 더 넉넉하게 쓸 수 있어요.");
  });
});
