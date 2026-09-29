import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import NotFound from "./NotFound";

describe("코스 없음 화면", () => {
  it("이유를 알려주고 돌아갈 길을 준다", () => {
    render(<NotFound message="링크가 잘못되었어요." />);
    expect(screen.getByRole("heading", { name: /코스를 찾을 수 없어요/ })).toBeTruthy();
    expect(screen.getByText("링크가 잘못되었어요.")).toBeTruthy();
    expect(screen.getByRole("link").getAttribute("href")).toBe("/");
  });
});
