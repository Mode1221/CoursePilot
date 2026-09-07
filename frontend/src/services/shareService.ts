// 공유 어댑터 레이어. 기본 Web Share API, 카카오 인앱 감지 시 카카오 SDK 폴백.

function isKakaoInApp(): boolean {
  if (typeof navigator === "undefined") return false;
  return /KAKAOTALK/i.test(navigator.userAgent);
}

export const shareService = {
  async share(url: string, title = "CoursePilot 코스"): Promise<void> {
    // 카카오 환경: 카카오 SDK 로드 시 공유 카드 폴백 (SDK 미로드면 표준 경로로)
    const kakao = (globalThis as any).Kakao;
    if (isKakaoInApp() && kakao?.Share) {
      kakao.Share.sendDefault({
        objectType: "feed",
        content: { title, description: "검증된 모임 동선", link: { webUrl: url, mobileWebUrl: url } },
      });
      return;
    }

    if (typeof navigator !== "undefined" && navigator.share) {
      await navigator.share({ title, url });
      return;
    }

    // 최종 폴백: 클립보드 복사
    await navigator.clipboard?.writeText(url);
  },
};
