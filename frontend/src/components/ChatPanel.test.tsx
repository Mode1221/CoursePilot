import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "./ChatPanel";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import { useUserStore } from "@/store/userStore";

vi.mock("@/services/api", () => ({
  api: {
    generate: vi.fn(),
    relax: vi.fn(),
    feedback: vi.fn().mockResolvedValue({ ok: true }),
    credits: vi.fn().mockResolvedValue({ questions_left: 3 }),
    complete: vi.fn(),
    satisfaction: vi.fn(),
    purchase: vi.fn(),
    messages: vi.fn().mockResolvedValue([]),
  },
}));

const COURSE = { id: "c1", title: "t", items: [], locked: false };

function setUser(userId: string | null) {
  useUserStore.setState({ userId, questionsLeft: 3 } as never);
}

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.mocked(api.generate).mockReset();
    vi.mocked(api.relax).mockReset();
    useCourseStore.setState({ course: COURSE, locked: false, messages: [], history: [] } as never);
    setUser("u1");
  });

  afterEach(cleanup);

  it("조건을 보내면 코스를 갱신한다", async () => {
    vi.mocked(api.generate).mockResolvedValue({
      course: { ...COURSE, title: "성수 코스" },
      relaxed: false,
      needs_confirmation: false,
    } as never);
    render(<ChatPanel courseId="c1" />);
    fireEvent.change(screen.getByLabelText("조건 입력"), { target: { value: "성수동 3시간" } });
    fireEvent.click(screen.getByText("전송"));
    await waitFor(() => expect(api.generate).toHaveBeenCalledWith("c1", "성수동 3시간", "u1"));
    await waitFor(() => expect(useCourseStore.getState().course?.title).toBe("성수 코스"));
  });

  it("장소가 부족하면 완화 여부를 묻고, 수락하면 완화 재시도를 호출한다", async () => {
    vi.mocked(api.generate).mockResolvedValue({
      course: COURSE,
      relaxed: false,
      needs_confirmation: true,
    } as never);
    vi.mocked(api.relax).mockResolvedValue({
      course: COURSE,
      relaxed: true,
      needs_confirmation: false,
    } as never);
    render(<ChatPanel courseId="c1" />);
    fireEvent.change(screen.getByLabelText("조건 입력"), { target: { value: "성수동" } });
    fireEvent.click(screen.getByText("전송"));
    const accept = await screen.findByText("완화 수락");
    fireEvent.click(accept);
    await waitFor(() => expect(api.relax).toHaveBeenCalledWith("c1", "u1"));
    expect(await screen.findByText(/완화된 조건으로 코스를 다시 구성했어요/)).toBeDefined();
  });

  it("비로그인 참여자는 입력이 잠긴다", () => {
    setUser(null);
    render(<ChatPanel courseId="c1" />);
    expect((screen.getByLabelText("조건 입력") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText("참여자는 수동 편집만 가능합니다")).toBeDefined();
  });
});
