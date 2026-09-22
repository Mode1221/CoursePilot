import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TogetherCards from "./TogetherCards";

const spec = {
  conditions: ["fresh", "normal", "tired", "hungry"],
  cravings: ["고기", "디저트", "아무거나"],
  dislikes: ["웨이팅", "매운 거", "없음"],
  budget_bands: [20000, 30000, 50000, 0],
};

afterEach(cleanup);

describe("TogetherCards", () => {
  it("땡기는 것·싫은 것을 고르지 않으면 보내지 않는다", async () => {
    const onSubmit = vi.fn();
    render(<TogetherCards spec={spec} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("보냈어요"));
    expect((await screen.findByRole("alert")).textContent).toMatch(/땡기는/);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("'아무거나'를 고르면 싫은 것 카드를 강조하고, 보낼 때는 조건에서 뺀다", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<TogetherCards spec={spec} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("아무거나"));
    expect(screen.getByText(/이것만 피할게요/)).toBeTruthy();
    fireEvent.click(screen.getByText("매운 거"));
    fireEvent.click(screen.getByText("피곤해 (많이 못 걸어)"));
    fireEvent.click(screen.getByText("~3만원"));
    fireEvent.click(screen.getByText("보냈어요"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith({
      condition: "tired",
      cravings: [],
      dislikes: ["매운 거"],
      budget_band: 30000,
      note: undefined,
    });
  });

  it("'아무거나'는 다른 취향과 함께 고를 수 없다", () => {
    render(<TogetherCards spec={spec} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("고기"));
    fireEvent.click(screen.getByText("아무거나"));
    expect(screen.getByText("고기").getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("아무거나").getAttribute("aria-pressed")).toBe("true");
  });
});
