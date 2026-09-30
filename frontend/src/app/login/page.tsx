"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import BrandMark from "@/components/BrandMark";
import SiteFooter from "@/components/SiteFooter";
import { Button, Input } from "@/components/ui";
import { ApiError, api, type LoginResult } from "@/services/api";
import { KAKAO_NEXT_KEY, KAKAO_STATE_KEY, finishLogin, kakaoRedirectUri } from "@/services/login";
import { readQuery, safeNext } from "@/services/nextPath";
import { useUserStore } from "@/store/userStore";

const PHONE_RE = /^01[016789]-?\d{3,4}-?\d{4}$/;

/**
 * 로그인. 체험을 다 쓴 사람, 두 번째로 온 사람, 세션이 만료된 사람이 온다.
 * 카카오(권장)와 전화 인증(SMS 가 켜진 환경에서만) 두 가지.
 */
export default function Login() {
  const router = useRouter();
  const { userId, kind, load, setUser } = useUserStore();
  const [next, setNext] = useState("/");
  const [reason, setReason] = useState<string | null>(null);
  const [kakaoId, setKakaoId] = useState<string | null>(null);
  const [phoneLogin, setPhoneLogin] = useState(false);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
    setNext(safeNext(readQuery("next")));
    if (readQuery("expired")) setReason("로그인이 만료됐어요. 다시 로그인해 주세요.");
    else if (readQuery("reason") === "trial")
      setReason("체험은 여기까지예요. 로그인하면 무료로 훨씬 더 쓸 수 있고, 체험 때 만든 코스도 그대로 이어져요.");
    api
      .publicConfig()
      .then((c) => {
        setKakaoId(c.kakao_login_client_id ?? null);
        setPhoneLogin(Boolean(c.phone_login));
      })
      .catch(() => {})
      .finally(() => setConfigLoaded(true));
  }, [load]);

  function kakao() {
    if (!kakaoId) return;
    const state = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    try {
      sessionStorage.setItem(KAKAO_STATE_KEY, state);
      sessionStorage.setItem(KAKAO_NEXT_KEY, next);
    } catch {
      /* 저장소가 막혀 있어도 로그인은 진행한다(돌아올 곳만 기본값) */
    }
    const url = new URL("https://kauth.kakao.com/oauth/authorize");
    url.searchParams.set("client_id", kakaoId);
    url.searchParams.set("redirect_uri", kakaoRedirectUri());
    url.searchParams.set("response_type", "code");
    url.searchParams.set("state", state);
    window.location.assign(url.toString());
  }

  async function sendCode() {
    if (busy) return;
    setError(null);
    if (!PHONE_RE.test(phone.trim())) {
      setError("휴대폰 번호를 010-0000-0000 형식으로 입력해 주세요.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.requestSmsCode(phone.trim());
      setCodeSent(true);
      if (res.dev_code) setCode(res.dev_code); // 개발 환경에서만 온다
    } catch (e) {
      setError(e instanceof ApiError && e.status === 429 ? "잠시 후 다시 요청해 주세요." : "인증번호를 보내지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const v = await api.verifySmsCode(phone.trim(), code.trim());
      const res: LoginResult =
        v.user_id && v.token ? { user_id: v.user_id, token: v.token, kind: "member", moved_courses: v.moved_courses } : await api.signup(phone.trim());
      finishLogin(res, setUser);
      router.replace(next);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "로그인하지 못했어요. 다시 시도해 주세요.");
      setBusy(false);
    }
  }

  const loggedIn = userId != null && kind === "member";

  return (
    <main className="cp-page">
      <BrandMark />
      <h1 className="cp-page__title">로그인</h1>
      {reason && (
        <p role="status" className="cp-page__lead">
          {reason}
        </p>
      )}

      {loggedIn ? (
        <div className="cp-panel" style={{ marginTop: "var(--sp-5)", display: "grid", gap: "var(--sp-3)" }}>
          <p style={{ margin: 0 }}>이미 로그인했어요.</p>
          <Button variant="primary" onClick={() => router.replace(next)}>
            계속하기
          </Button>
        </div>
      ) : (
        <div className="cp-panel" style={{ marginTop: "var(--sp-5)", display: "grid", gap: "var(--sp-4)" }}>
          {kakaoId && (
            <button
              type="button"
              onClick={kakao}
              style={{
                minHeight: 50,
                border: "none",
                borderRadius: "var(--r-full)",
                background: "#FEE500",
                color: "rgba(0,0,0,0.85)",
                fontSize: "var(--fs-md)",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              카카오로 계속하기
            </button>
          )}

          {phoneLogin && (
            <fieldset style={{ border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "var(--sp-4)" }}>
              <legend style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)", padding: "0 var(--sp-1)" }}>
                전화번호로 로그인
              </legend>
              <div style={{ display: "flex", gap: "var(--sp-2)" }}>
                <Input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="010-0000-0000"
                  inputMode="tel"
                  aria-label="휴대폰 번호"
                  style={{ flex: 1, fontSize: 16 }}
                />
                <Button onClick={sendCode} disabled={busy}>
                  {codeSent ? "다시 받기" : "인증번호 받기"}
                </Button>
              </div>
              {codeSent && (
                <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-2)" }}>
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="인증번호 6자리"
                    inputMode="numeric"
                    aria-label="인증번호"
                    style={{ flex: 1, fontSize: 16 }}
                  />
                  <Button variant="primary" onClick={verify} disabled={busy || code.trim().length !== 6}>
                    로그인
                  </Button>
                </div>
              )}
              <p style={{ fontSize: "var(--fs-xs)", color: "var(--text-faint)", marginTop: "var(--sp-2)" }}>
                처음이면 이 번호로 가입돼요. <Link href="/terms">이용약관</Link>·
                <Link href="/privacy">개인정보처리방침</Link>에 동의하는 것으로 봐요.
              </p>
            </fieldset>
          )}

          {configLoaded && !kakaoId && !phoneLogin && (
            <p role="status" style={{ color: "var(--text-muted)" }}>
              로그인을 준비하고 있어요. 잠시 후 다시 들러 주세요.
            </p>
          )}

          {error && (
            <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--fs-sm)" }}>
              {error}
            </p>
          )}

          <p style={{ margin: 0, fontSize: "var(--fs-xs)", color: "var(--text-faint)" }}>
            카카오 로그인은 회원 구분용 번호만 받아요. 이름·이메일·프로필은 받지 않아요. 계속하면{" "}
            <Link href="/terms">이용약관</Link>과 <Link href="/privacy">개인정보처리방침</Link>(만 14세 이상, 생성형
            AI 이용, 일본 서버·미국 AI 사업자로의 국외 이전 포함)에 동의하는 것으로 봐요.
          </p>
        </div>
      )}

      {!userId && (
        <p style={{ marginTop: "var(--sp-6)", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          처음이에요?{" "}
          <Link href="/start" style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
            가입 없이 한 번 써 보기
          </Link>
        </p>
      )}
      <SiteFooter />
    </main>
  );
}
