import { beforeEach, describe, expect, it } from "vitest";

import { useCourseStore } from "./courseStore";
import type { Course, TimelineItem } from "@/types";

function item(id: string, lat: number, lng: number): TimelineItem {
  return { place: { id, name: id, lat, lng }, travel_to_next: null };
}

const course: Course = {
  id: "c1",
  title: "t",
  items: [item("a", 37.54, 127.05), item("b", 37.55, 127.06), item("c", 37.56, 127.07)],
  locked: false,
};

describe("courseStore 수동 편집", () => {
  beforeEach(() => {
    useCourseStore.setState({ course: structuredClone(course), locked: false });
  });

  it("reorder가 순서를 바꾸고 이동시간을 재계산", async () => {
    await useCourseStore.getState().reorder(0, 2);
    const items = useCourseStore.getState().course!.items;
    expect(items.map((i) => i.place.id)).toEqual(["b", "c", "a"]);
    // 마지막을 제외한 각 항목은 다음 구간 이동정보를 가진다
    expect(items[0].travel_to_next?.duration_min).toBeGreaterThan(0);
    expect(items[2].travel_to_next).toBeNull();
  });

  it("locked 상태에서는 편집이 차단된다", async () => {
    useCourseStore.setState({ locked: true });
    await useCourseStore.getState().remove(0);
    expect(useCourseStore.getState().course!.items).toHaveLength(3);
  });
});
