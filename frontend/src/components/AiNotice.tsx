/**
 * AI 사용 고지 (AI 기본법 사전 고지). 코스가 있는 화면마다 한 줄로 보인다.
 * 문구는 백엔드 설정(ai_notice)과 같은 뜻으로 두되, 렌더는 여기서 고정한다
 * (공유 화면은 로그인 없이 열리므로 별도 조회 없이 항상 노출).
 */
export const AI_NOTICE = "AI가 만든 추천이에요. 영업시간·휴무는 방문 전 한 번 더 확인해 주세요.";

export default function AiNotice() {
  return (
    <p
      role="note"
      style={{
        margin: "var(--sp-2) 0 0",
        fontSize: "var(--fs-xs)",
        color: "var(--text-faint)",
      }}
    >
      {AI_NOTICE}
    </p>
  );
}
