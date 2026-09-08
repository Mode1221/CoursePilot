import { toast } from "@/store/toastStore";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/** 코스를 .ics 로 내려받아 캘린더 앱에 넣게 한다. */
export function saveCalendar(courseId: string): void {
  const url = `${BASE}/courses/${courseId}/calendar.ics`;
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = `coursepilot-${courseId}.ics`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast("캘린더 파일을 저장했어요.", "success");
  } catch {
    toast("캘린더 파일을 저장하지 못했어요.", "error");
  }
}
