import { describe, expect, it } from "vitest";
import { hoursFreshnessLabel, yearsOpen } from "./placeFacts";
import type { Place } from "@/types";

const base: Place = { id: "p", name: "가게", lat: 37.5, lng: 127.0 };

describe("yearsOpen", () => {
  it("인허가일자가 없으면 표시하지 않는다", () => {
    expect(yearsOpen(base)).toBeNull();
  });

  it("1년 미만은 표시하지 않는다", () => {
    expect(yearsOpen({ ...base, opened_on: "2026-01-01" }, new Date("2026-09-09"))).toBeNull();
  });

  it("년차를 내림으로 계산한다", () => {
    expect(yearsOpen({ ...base, opened_on: "2015-03-01" }, new Date("2026-09-09"))).toBe(11);
  });

  it("잘못된 날짜는 무시한다", () => {
    expect(yearsOpen({ ...base, opened_on: "언제였더라" })).toBeNull();
  });
});

describe("hoursFreshnessLabel", () => {
  it("확인 이력이 없으면 표시하지 않는다", () => {
    expect(hoursFreshnessLabel(base)).toBeNull();
  });

  it("오늘 확인했으면 오늘로 표시한다", () => {
    const now = new Date("2026-09-09T12:00:00Z");
    expect(hoursFreshnessLabel({ ...base, hours_checked_at: "2026-09-09T01:00:00Z" }, now)).toBe(
      "오늘 확인",
    );
  });

  it("며칠 지났는지 센다", () => {
    const now = new Date("2026-09-09T12:00:00Z");
    expect(hoursFreshnessLabel({ ...base, hours_checked_at: "2026-09-06T12:00:00Z" }, now)).toBe(
      "3일 전 확인",
    );
  });

  it("잘못된 값은 무시한다", () => {
    expect(hoursFreshnessLabel({ ...base, hours_checked_at: "어제쯤" })).toBeNull();
  });
});
