import { ApiError, api } from "@/services/api";
import { toast } from "@/store/toastStore";

/**
 * 새 코스를 만들고 그 화면 주소를 돌려준다. 한도에 걸리면 api 가 체험 시작·로그인 화면으로
 * 보내므로 여기서는 null 만 돌려준다(오늘 몫·서비스 몫이 찬 경우엔 이유를 알린다).
 */
export async function createCourseUrl(seed?: string | null): Promise<string | null> {
  try {
    const course = await api.createCourse();
    const q = seed ? `?seed=${encodeURIComponent(seed)}` : "";
    return `/plan/${course.id}${q}`;
  } catch (e) {
    if (e instanceof ApiError && (e.code === "login_required" || e.code === "guest_required")) return null;
    toast(e instanceof ApiError ? e.message : "코스를 만들지 못했어요. 잠시 후 다시 시도해주세요.", "error");
    return null;
  }
}
