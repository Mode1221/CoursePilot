import { fetchCourse } from "@/services/ogData";
import { OG_CONTENT_TYPE, OG_SIZE, renderOgCard } from "@/services/ogImage";
import { courseText } from "@/services/ogText";

// 완성된 코스 공유 링크의 미리보기 이미지: 코스 이름·날짜·지역·장소 순서. 없으면 일반 카드.
export const alt = "같이 정한 데이트 코스";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return renderOgCard(courseText(await fetchCourse(id)).card);
}
