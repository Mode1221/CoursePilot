import type { Place } from "@/types";

/** 인허가일자 → 영업 년차(1년 미만은 표시하지 않는다 — "0년차"는 의미가 없다). */
export function yearsOpen(place: Place, now: Date = new Date()): number | null {
  if (!place.opened_on) return null;
  const opened = new Date(place.opened_on);
  if (Number.isNaN(opened.getTime())) return null;
  const years = Math.floor((now.getTime() - opened.getTime()) / (365.25 * 24 * 3600 * 1000));
  return years >= 1 ? years : null;
}

/** 영업시간을 마지막으로 확인한 지 며칠 됐는지. 오늘 확인했으면 0, 모르면 null. */
export function hoursCheckedDaysAgo(place: Place, now: Date = new Date()): number | null {
  if (!place.hours_checked_at) return null;
  const checked = new Date(place.hours_checked_at);
  if (Number.isNaN(checked.getTime())) return null;
  const days = Math.floor((now.getTime() - checked.getTime()) / (24 * 3600 * 1000));
  return days >= 0 ? days : null;
}

/** "오늘 확인" / "3일 전 확인". 확인 이력이 없으면 null. */
export function hoursFreshnessLabel(place: Place, now: Date = new Date()): string | null {
  const days = hoursCheckedDaysAgo(place, now);
  if (days === null) return null;
  return days === 0 ? "오늘 확인" : `${days}일 전 확인`;
}
