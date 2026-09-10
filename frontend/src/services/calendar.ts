import { toast } from "@/store/toastStore";

import { apiBase } from "@/services/apiBase";

/** 코스를 .ics 로 내려받아 캘린더 앱에 넣게 한다. */
export function saveCalendar(courseId: string): void {
  const url = `${apiBase()}/courses/${courseId}/calendar.ics`;
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
