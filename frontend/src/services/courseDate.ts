const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** "2026-09-12" → "9월 12일 (토)". 값이 없거나 형식이 다르면 null. */
export function formatPlanDate(value?: string | null): string | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return null;
  const [, y, mo, day] = m;
  const date = new Date(Number(y), Number(mo) - 1, Number(day));
  if (Number.isNaN(date.getTime())) return null;
  return `${Number(mo)}월 ${Number(day)}일 (${WEEKDAYS[date.getDay()]})`;
}
