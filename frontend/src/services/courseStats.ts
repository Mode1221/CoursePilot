import type { Course } from "@/types";

export interface CourseStats {
  places: number;
  travelMin: number; // 구간 이동시간 합
  totalMin: number; // 첫 도착 ~ 마지막 출발
  costPerPerson: number; // 가격이 있는 장소들의 1인 예상 합계(원)
  costKnown: number; // 가격 정보를 가진 장소 수
  costEstimated: boolean; // 합계에 카테고리 추정가가 섞였는지
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
  const priced = items.filter((it) => typeof it.place.price === "number");
  const costPerPerson = priced.reduce((sum, it) => sum + (it.place.price ?? 0), 0);
  return {
    places: items.length,
    travelMin,
    totalMin,
    costPerPerson,
    costKnown: priced.length,
    // 추정가가 하나라도 섞이면 합계를 확정 금액처럼 보여주면 안 된다
    costEstimated: priced.some((it) => it.place.price_estimated === true),
  };
}

/** "3시간 20분" / "40분" */
export function formatDuration(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m}분`;
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}

/** "4.5만원" / "8천원". 0이면 null. */
export function formatCost(won: number): string | null {
  if (won <= 0) return null;
  if (won >= 10_000) {
    const man = won / 10_000;
    return `${Number.isInteger(man) ? man : man.toFixed(1)}만원`;
  }
  return `${Math.round(won / 1000)}천원`;
}
