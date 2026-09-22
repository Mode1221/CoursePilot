import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AttributionChips from "./AttributionChips";

describe("AttributionChips", () => {
  it("누구의 무엇이 어디에 반영됐는지 보인다", () => {
    render(<AttributionChips items={[{ who: "지은", what: "피곤해", effect: "이동 10분 이내" }]} />);
    expect(screen.getByRole("list", { name: "반영된 의견" }).textContent).toMatch(/지은 피곤해\s*→\s*이동 10분 이내/);
  });
  it("없으면 아무것도 그리지 않는다", () => {
    const { container } = render(<AttributionChips items={[]} />);
    expect(container.innerHTML).toBe("");
  });
});
