import { formatPlanDate } from "@/services/courseDate";
import type { Course } from "@/types";

/** 공유 미리보기용 한 줄 요약: "성수동 · 카페 → 전시 → 식당" (최대 4곳). */
export function summarize(course: Course): string {
  const names = course.items.map((it) => it.place.name);
  if (names.length === 0) return "아직 장소가 없는 코스예요.";
  const head = names.slice(0, 4).join(" → ");
  const more = names.length > 4 ? ` 외 ${names.length - 4}곳` : "";
  const region = course.region ? `${course.region} · ` : "";
  const day = formatPlanDate(course.plan_date);
  const prefix = day ? `${day} · ${region}` : region;
  return `${prefix}${head}${more}`;
}
