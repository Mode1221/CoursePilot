import { fetchTogetherPreview } from "@/services/ogData";
import { OG_CONTENT_TYPE, OG_SIZE, renderOgCard } from "@/services/ogImage";
import { inviteText } from "@/services/ogText";

// 상대에게 카톡으로 가는 초대 링크의 미리보기 이미지. 토큰이 틀리거나 서버가 안 되면 일반 초대 카드.
export const alt = "데이트 코스를 같이 정하자는 초대";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return renderOgCard(inviteText(await fetchTogetherPreview(token)).card);
}
