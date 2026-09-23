import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AttributionChips from "./AttributionChips";

describe("AttributionChips", () => {
  it("누구의 무엇이 어디에 반영됐는지 보인다", () => {
    render(<AttributionChips items={[{ who: "지은", what: "피곤해", effect: "이동 10분 이내" }]} />);
    const list = screen.getByRole("list", { name: "반영된 의견" });
    // 화면엔 결과 위주로 짧게, 전체 문장은 aria-label 로
    expect(list.textContent).toContain("이동 10분 이내");
    expect(list.textContent).toContain("피곤해");
    expect(screen.getByLabelText("지은 피곤해 → 이동 10분 이내")).toBeTruthy();
  });
  it("없으면 아무것도 그리지 않는다", () => {
    const { container } = render(<AttributionChips items={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("반복되는 말을 줄이고 못 찾은 취향은 점선으로", async () => {
    const { chipText } = await import("./AttributionChips");
    expect(chipText({ who: "민수", what: "시끄러운 곳", effect: "시끄러운 곳 빼기" })).toEqual({ main: "시끄러운 곳 빼기", why: null, kind: "normal" });
    expect(chipText({ who: "민수", what: "많이 걷기", effect: "이동 12분 이내로" }).main).toBe("이동 12분 이내");
    expect(chipText({ who: "민수", what: "예산", effect: "예산 맞춤" }).why).toBeNull();
    expect(chipText({ who: "민수", what: "한식", effect: "식사 칸", slot: "meal" })).toEqual({ main: "한식", why: "민수 취향", kind: "normal" });
    expect(chipText({ who: "지은", what: "디저트", effect: "맞는 곳을 못 찾았어요 · 교체에서 골라보세요" }).kind).toBe("unmet");
  });
});
