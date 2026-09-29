import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AiNotice, { AI_NOTICE } from "./AiNotice";

describe("AiNotice", () => {
  it("AI 사용 고지를 note 로 보인다", () => {
    render(<AiNotice />);
    expect(screen.getByRole("note").textContent).toBe(AI_NOTICE);
    expect(AI_NOTICE).toMatch(/AI/);
  });
});
