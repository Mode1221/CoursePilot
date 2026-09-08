import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCourseStore } from "./courseStore";
import { api } from "@/services/api";
import type { Course, TimelineItem } from "@/types";

vi.mock("@/services/api", () => ({
  api: { setItems: vi.fn(), addPlace: vi.fn() },
}));

function item(id: string): TimelineItem {
  return { place: { id, name: id, lat: 37.54, lng: 127.05 }, travel_to_next: null };
}

const course: Course = {
  id: "c1",
  title: "t",
  items: [item("a"), item("b"), item("c")],
  locked: false,
};

describe("courseStore 되돌리기", () => {
  beforeEach(() => {
    vi.mocked(api.setItems).mockReset();
    vi.mocked(api.setItems).mockResolvedValue(structuredClone(course));
    useCourseStore.setState({ course: structuredClone(course), locked: false, history: [] });
  });

  it("편집 전에는 되돌릴 수 없다", () => {
    expect(useCourseStore.getState().canUndo()).toBe(false);
  });

  it("삭제 후 되돌리면 편집 직전 구성으로 복원 요청한다", async () => {
    await useCourseStore.getState().remove(1);
    expect(useCourseStore.getState().course!.items.map((i) => i.place.id)).toEqual(["a", "c"]);
    expect(useCourseStore.getState().canUndo()).toBe(true);

    await useCourseStore.getState().undo();
    expect(api.setItems).toHaveBeenLastCalledWith("c1", ["a", "b", "c"]);
    expect(useCourseStore.getState().course!.items.map((i) => i.place.id)).toEqual(["a", "b", "c"]);
    expect(useCourseStore.getState().canUndo()).toBe(false);
  });

  it("여러 편집을 순서대로 되감는다", async () => {
    await useCourseStore.getState().remove(2); // a,b
    await useCourseStore.getState().reorder(0, 1); // b,a
    expect(useCourseStore.getState().history).toEqual([
      ["a", "b", "c"],
      ["a", "b"],
    ]);
    await useCourseStore.getState().undo();
    expect(api.setItems).toHaveBeenLastCalledWith("c1", ["a", "b"]);
  });

  it("locked 상태에서는 되돌리기가 차단된다", async () => {
    await useCourseStore.getState().remove(0);
    vi.mocked(api.setItems).mockClear();
    useCourseStore.setState({ locked: true });
    await useCourseStore.getState().undo();
    expect(api.setItems).not.toHaveBeenCalled();
  });
});
