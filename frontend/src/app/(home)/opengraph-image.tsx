import { OG_CONTENT_TYPE, OG_SIZE, renderOgCard } from "@/services/ogImage";
import { DEFAULT_CARD } from "@/services/ogText";

// 사이트 기본 미리보기(랜딩·약관 등 따로 정하지 않은 화면)
export const alt = "픽앤어스 — 둘이 같이 정하는 데이트 코스";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default function Image() {
  return renderOgCard(DEFAULT_CARD);
}
