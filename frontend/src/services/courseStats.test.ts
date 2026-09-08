import { describe, expect, it } from "vitest";

import { courseStats, formatDuration } from "./courseStats";
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
    expect(s).toEqual({ places: 2, travelMin: 15, totalMin: 180 });
  });

  it("자정을 넘기면 하루를 더한다", () => {
    const s = courseStats(course([item("a", "22:00", "23:00", 20), item("b", "23:20", "01:00")]));
    expect(s.totalMin).toBe(180);
  });

  it("빈 코스는 0", () => {
    expect(courseStats(course([]))).toEqual({ places: 0, travelMin: 0, totalMin: 0 });
  });
});

describe("formatDuration", () => {
  it("시간과 분을 사람이 읽는 형태로", () => {
    expect(formatDuration(200)).toBe("3시간 20분");
    expect(formatDuration(120)).toBe("2시간");
    expect(formatDuration(40)).toBe("40분");
  });
});
