import { describe, expect, it } from "vitest";

import { formatPlanDate } from "./courseDate";

describe("formatPlanDate", () => {
  it("날짜를 요일과 함께 보여준다", () => {
    expect(formatPlanDate("2026-09-12")).toBe("9월 12일 (토)");
  });

  it("값이 없으면 null", () => {
    expect(formatPlanDate(null)).toBeNull();
    expect(formatPlanDate(undefined)).toBeNull();
  });

  it("형식이 다르면 null", () => {
    expect(formatPlanDate("2026/09/12")).toBeNull();
  });
});
