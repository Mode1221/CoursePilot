import { describe, expect, it } from "vitest";

import { courseToText } from "./courseText";
import type { Course, TimelineItem } from "@/types";

function item(name: string, arrive?: string, depart?: string, travel?: number): TimelineItem {
  return {
    place: { id: name, name, lat: 37.5, lng: 127 },
    arrive,
    depart,
    travel_to_next: travel
      ? { from_place_id: name, to_place_id: "x", mode: "walk", duration_min: travel, distance_m: 1 }
      : null,
  };
}

function course(items: TimelineItem[]): Course {
  return { id: "c1", title: "성수동 데이트", items, locked: false };
}

describe("courseToText", () => {
  it("순번·시간·이동수단을 담은 텍스트를 만든다", () => {
    const text = courseToText(course([item("카페", "13:00:00", "14:00:00", 12), item("전시", "14:12:00", "16:00:00")]));
    expect(text).toBe(
      ["성수동 데이트", "1. 카페 (13:00~14:00)", "   ↳ 도보 12분", "2. 전시 (14:12~16:00)"].join("\n"),
    );
  });

  it("시간이 없으면 이름만 넣는다", () => {
    expect(courseToText(course([item("카페")]))).toBe("성수동 데이트\n1. 카페");
  });

  it("빈 코스는 안내 문구", () => {
    expect(courseToText(course([]))).toContain("아직 장소가 없어요");
  });

  it("공유 링크를 마지막에 붙인다", () => {
    const text = courseToText(course([item("카페")]), "https://x/share/c1");
    expect(text.endsWith("\nhttps://x/share/c1")).toBe(true);
  });
});
