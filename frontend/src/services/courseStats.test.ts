import { describe, expect, it } from "vitest";

import { courseStats, formatCost, formatDuration } from "./courseStats";
import type { Course, TimelineItem } from "@/types";

function item(id: string, arrive: string, depart: string, travel?: number): TimelineItem {
  return {
    place: { id, name: id, lat: 37.5, lng: 127 },
    arrive,
    depart,
    travel_to_next: travel
      ? { from_place_id: id, to_place_id: "x", mode: "walk", duration_min: travel, distance_m: 100 }
      : null,
  };
}

function course(items: TimelineItem[]): Course {
  return { id: "c", title: "t", items, locked: false };
}

describe("courseStats", () => {
  it("장소 수·이동시간·총 소요시간을 계산한다", () => {
    const s = courseStats(course([item("a", "13:00", "14:00", 15), item("b", "14:15", "16:00")]));
    expect(s).toMatchObject({ places: 2, travelMin: 15, totalMin: 180 });
  });

  it("자정을 넘기면 하루를 더한다", () => {
    const s = courseStats(course([item("a", "22:00", "23:00", 20), item("b", "23:20", "01:00")]));
    expect(s.totalMin).toBe(180);
  });

  it("빈 코스는 0", () => {
    expect(courseStats(course([]))).toMatchObject({ places: 0, travelMin: 0, totalMin: 0 });
  });
});

describe("formatDuration", () => {
  it("시간과 분을 사람이 읽는 형태로", () => {
    expect(formatDuration(200)).toBe("3시간 20분");
    expect(formatDuration(120)).toBe("2시간");
    expect(formatDuration(40)).toBe("40분");
  });
});

it("가격이 있는 장소만 1인 비용으로 합산한다", () => {
  const course = {
    id: "c",
    title: "t",
    locked: false,
    items: [
      { place: { id: "a", name: "A", lat: 0, lng: 0, price: 20000 }, travel_to_next: null },
      { place: { id: "b", name: "B", lat: 0, lng: 0 }, travel_to_next: null },
    ],
  } as unknown as Course;
  const stats = courseStats(course);
  expect(stats.costPerPerson).toBe(20000);
  expect(stats.costKnown).toBe(1);
});

it("금액을 사람이 읽기 좋게 만든다", () => {
  expect(formatCost(45000)).toBe("4.5만원");
  expect(formatCost(20000)).toBe("2만원");
  expect(formatCost(8000)).toBe("8천원");
  expect(formatCost(0)).toBeNull();
});

describe("추정가 표시", () => {
  const item = (price: number | undefined, estimated?: boolean) => ({
    place: {
      id: `p${price}`,
      name: "장소",
      lat: 37.5,
      lng: 127.0,
      price,
      price_estimated: estimated,
    },
    arrive: "12:00",
    depart: "13:00",
  });

  it("추정가가 섞이면 표시한다", () => {
    const course = { id: "c", title: "t", items: [item(10000, true), item(5000)] } as never;
    expect(courseStats(course).costEstimated).toBe(true);
  });

  it("실제 가격만 있으면 표시하지 않는다", () => {
    const course = { id: "c", title: "t", items: [item(10000), item(5000)] } as never;
    expect(courseStats(course).costEstimated).toBe(false);
  });

  it("가격이 없는 장소는 합계에서 빠진다", () => {
    const course = { id: "c", title: "t", items: [item(10000), item(undefined)] } as never;
    const stats = courseStats(course);
    expect(stats.costPerPerson).toBe(10000);
    expect(stats.costKnown).toBe(1);
  });
});
