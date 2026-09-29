import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TogetherPage from "./page";
import { readAcquisition } from "@/services/acquisition";
import { api } from "@/services/api";
import { useUserStore } from "@/store/userStore";

vi.mock("next/navigation", () => ({ useParams: () => ({ token: "AbC_def-123456" }) }));
vi.mock("@/services/api", async (orig) => ({
  ...(await orig<typeof import("@/services/api")>()),
  api: { togetherStatus: vi.fn(), togetherPartnerInput: vi.fn() },
}));

const STATUS = {
  course_id: "c1",
  owner_name: "민수",
  partner_name: "상대",
  submitted: [],
  built: false,
  request_text: "토요일 3시 성수",
  cards: { conditions: ["보통"], cravings: ["카페"], dislikes: ["웨이팅"], budget_bands: [3] },
  invite_reward: { days: 7, extra: { course: 5, ai: 20, build: 5 } },
};

describe("같이 정하기 화면의 초대 보상 안내", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(api.togetherStatus).mockResolvedValue(STATUS as never);
  });
  afterEach(cleanup);

  it("회원이 아니면 가입 시 두 사람 모두 받는 보상을 한 줄로 알려 주고 링크 토큰을 기억한다", async () => {
    useUserStore.setState({ userId: null, kind: null, load: () => {} } as never);
    render(<TogetherPage />);
    expect(await screen.findByText(/두 사람 모두 7일 동안 하루 코스 5개씩 더/)).toBeDefined();
    expect(readAcquisition().invite).toBe("AbC_def-123456");
  });

  it("이미 회원이면 보상 안내가 없다(새 가입만 대상)", async () => {
    useUserStore.setState({ userId: "u1", kind: "member", load: () => {} } as never);
    render(<TogetherPage />);
    expect(await screen.findByText("토요일 3시 성수")).toBeDefined();
    expect(screen.queryByText(/두 사람 모두/)).toBeNull();
  });
});
