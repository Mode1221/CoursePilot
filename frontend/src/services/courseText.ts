import { formatPlanDate } from "@/services/courseDate";
import type { Course } from "@/types";
import { MODE_LABEL } from "@/types";

/** 메신저에 붙여넣기 좋은 코스 텍스트.
 *
 * 예)
 * 성수동 데이트
 * 1. 카페 A (13:00~14:00)
 *    ↳ 도보 12분
 * 2. 전시 B (14:12~16:00)
 */
export function courseToText(course: Course, shareUrl?: string): string {
  const day = formatPlanDate(course.plan_date);
  const lines: string[] = [day ? `${course.title} — ${day}` : course.title];
  course.items.forEach((item, i) => {
    const time =
      item.arrive && item.depart ? ` (${item.arrive.slice(0, 5)}~${item.depart.slice(0, 5)})` : "";
    lines.push(`${i + 1}. ${item.place.name}${time}`);
    if (item.travel_to_next) {
      const t = item.travel_to_next;
      lines.push(`   ↳ ${MODE_LABEL[t.mode]} ${t.duration_min}분`);
    }
  });
  if (course.items.length === 0) lines.push("(아직 장소가 없어요)");
  if (shareUrl) lines.push("", shareUrl);
  return lines.join("\n");
}
