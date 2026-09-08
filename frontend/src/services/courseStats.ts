import type { Course } from "@/types";

export interface CourseStats {
  places: number;
  travelMin: number; // 구간 이동시간 합
  totalMin: number; // 첫 도착 ~ 마지막 출발
}

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

/** 타임라인 요약: 장소 수, 총 이동시간, 전체 소요시간(자정 넘김 보정). */
export function courseStats(course: Course): CourseStats {
  const items = course.items;
  const travelMin = items.reduce((sum, it) => sum + (it.travel_to_next?.duration_min ?? 0), 0);

  const first = items[0]?.arrive;
  const last = items[items.length - 1]?.depart;
  let totalMin = 0;
  if (first && last) {
    totalMin = toMinutes(last) - toMinutes(first);
    if (totalMin < 0) totalMin += 24 * 60; // 자정을 넘긴 코스
  }
  return { places: items.length, travelMin, totalMin };
}

/** "3시간 20분" / "40분" */
export function formatDuration(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m}분`;
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}
