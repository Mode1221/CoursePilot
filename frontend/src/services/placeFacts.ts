import type { Place } from "@/types";

/** 인허가일자 → 영업 년차(1년 미만은 표시하지 않는다 — "0년차"는 의미가 없다). */
export function yearsOpen(place: Place, now: Date = new Date()): number | null {
  if (!place.opened_on) return null;
  const opened = new Date(place.opened_on);
  if (Number.isNaN(opened.getTime())) return null;
  const years = Math.floor((now.getTime() - opened.getTime()) / (365.25 * 24 * 3600 * 1000));
  return years >= 1 ? years : null;
}
