import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SiteFooter from "./SiteFooter";

describe("SiteFooter", () => {
  it("약관·개인정보처리방침으로 가는 링크가 있다", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("link", { name: "이용약관" }).getAttribute("href")).toBe("/terms");
    expect(screen.getByRole("link", { name: "개인정보처리방침" }).getAttribute("href")).toBe(
      "/privacy",
    );
  });
});
