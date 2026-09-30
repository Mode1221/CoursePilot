"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "@/services/api";
import { KAKAO_NEXT_KEY, KAKAO_STATE_KEY, finishLogin, kakaoRedirectUri } from "@/services/login";
import { readQuery, safeNext } from "@/services/nextPath";
import { useUserStore } from "@/store/userStore";

/**
 * 카카오 인가 화면에서 돌아오는 곳. state 가 로그인 버튼을 누를 때 저장한 값과 같아야만
 * 코드를 서버로 보낸다(남이 만든 로그인 링크로 엉뚱한 계정에 들어가는 것을 막는다).
 */
export default function KakaoCallback() {
  const router = useRouter();
  const { setUser } = useUserStore();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false); // 개발 모드 이중 실행으로 같은 코드를 두 번 쓰지 않게

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = readQuery("code");
    const state = readQuery("state");
    let saved: string | null = null;
    let next = "/";
    try {
      saved = sessionStorage.getItem(KAKAO_STATE_KEY);
      next = safeNext(sessionStorage.getItem(KAKAO_NEXT_KEY));
      sessionStorage.removeItem(KAKAO_STATE_KEY);
      sessionStorage.removeItem(KAKAO_NEXT_KEY);
    } catch {
      /* 저장소가 막혀 있으면 state 검증을 못 한다 → 아래에서 실패 처리 */
    }
    if (readQuery("error")) {
      setError("카카오 로그인을 취소했어요.");
      return;
    }
    if (!code || !state || !saved || state !== saved) {
      setError("로그인 요청이 만료됐어요. 다시 시도해 주세요.");
      return;
    }
    api
      .kakaoLogin(code, kakaoRedirectUri())
      .then((res) => {
        finishLogin(res, setUser);
        router.replace(next);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "카카오 로그인에 실패했어요."));
  }, [router, setUser]);

  return (
    <main style={{ padding: "var(--sp-12) var(--sp-4)", maxWidth: 460, margin: "0 auto" }}>
      {error ? (
        <>
          <h1 className="cp-page__title">로그인하지 못했어요</h1>
          <p role="alert" style={{ color: "var(--text-muted)" }}>
            {error}
          </p>
          <Link href="/login" style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
            로그인 화면으로
          </Link>
        </>
      ) : (
        <p role="status" style={{ color: "var(--text-muted)" }}>
          카카오 로그인 중…
        </p>
      )}
    </main>
  );
}
