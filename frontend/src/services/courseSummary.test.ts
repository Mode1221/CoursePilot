import { describe, expect, it } from "vitest";

import { summarize } from "./courseSummary";
import type { Course, TimelineItem } from "@/types";

function item(name: string): TimelineItem {
  return { place: { id: name, name, lat: 37.5, lng: 127 }, travel_to_next: null };
}

function course(names: string[], region?: string): Course {
  return { id: "c1", title: "t", region, items: names.map(item), locked: false };
}

describe("공유 OG 요약", () => {
  it("지역과 장소를 화살표로 잇는다", () => {
    expect(summarize(course(["카페", "전시"], "성수동"))).toBe("성수동 · 카페 → 전시");
  });

  it("4곳을 넘으면 나머지는 개수로 접는다", () => {
    expect(summarize(course(["a", "b", "c", "d", "e", "f"]))).toBe("a → b → c → d 외 2곳");
  });

  it("빈 코스는 안내 문구", () => {
    expect(summarize(course([]))).toBe("아직 장소가 없는 코스예요.");
  });
});

it("날짜와 인원수를 함께 보여준다", () => {
  const course = {
    id: "c1",
    title: "t",
    region: "성수동",
    plan_date: "2026-09-12",
    party_size: 4,
    locked: false,
    items: [{ place: { id: "p1", name: "카페 A", category: "cafe", lat: 0, lng: 0 } }],
  } as unknown as Course;
  expect(summarize(course)).toBe("9월 12일 (토) · 4명 · 성수동 · 카페 A");
});
