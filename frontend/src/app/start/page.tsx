"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import BrandMark from "@/components/BrandMark";
import SiteFooter from "@/components/SiteFooter";
import { Button, Input } from "@/components/ui";
import { ApiError, api } from "@/services/api";
import { createCourseUrl } from "@/services/newCourse";
import { NEW_COURSE, readQuery, safeNext } from "@/services/nextPath";
import { useUserStore } from "@/store/userStore";

/**
 * 로그인 없이 한 번 써 보기. 부를 이름(선택)과 동의만 받는다.
 * 서버가 체험 계정을 만들어 주고, 체험 몫(코스 1개·AI 수정 몇 번)을 다 쓰면 로그인으로 넘어간다.
 */
export default function StartTrial() {
  const router = useRouter();
  const { userId, load, setUser } = useUserStore();
  const [nickname, setNickname] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [next, setNext] = useState<string>(NEW_COURSE);
  const [seed, setSeed] = useState<string | null>(null);

  useEffect(() => {
    load();
    setNext(readQuery("next") ?? NEW_COURSE);
    setSeed(readQuery("seed"));
  }, [load]);

  async function go() {
    const target = next === NEW_COURSE ? await createCourseUrl(seed) : safeNext(next);
    if (target) router.replace(target);
    else setBusy(false);
  }

  async function start() {
    if (busy) return;
    setError(null);
    if (!agreed) {
      setError("이용약관과 개인정보처리방침에 동의해 주세요.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.startGuest(nickname.trim() || null, true);
      setUser(res.user_id, res.token, "guest");
      await go();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "시작하지 못했어요. 잠시 후 다시 시도해 주세요.");
      setBusy(false);
    }
  }

  const loginHref = `/login?next=${encodeURIComponent(next === NEW_COURSE ? "/" : safeNext(next))}`;

  return (
    <main className="cp-page">
      <BrandMark />
      <h1 className="cp-page__title">가입 없이 한 번 써 보기</h1>
      <p className="cp-page__lead">
        코스 하나를 만들고, 상대에게 링크를 보내 같이 정하는 것까지 해 볼 수 있어요. 더 쓰고 싶으면 그때
        로그인하면 돼요 — 만든 코스는 그대로 이어져요.
      </p>

      {userId ? (
        <div className="cp-panel" style={{ display: "grid", gap: "var(--sp-3)" }}>
          <p style={{ margin: 0 }}>이미 시작했어요.</p>
          <Button variant="primary" onClick={() => { setBusy(true); void go(); }} disabled={busy}>
            {busy ? "여는 중…" : "이어서 하기"}
          </Button>
        </div>
      ) : (
        <div className="cp-panel">
          <label style={{ display: "block", fontSize: "var(--fs-sm)", fontWeight: 600, color: "var(--text)" }}>
            뭐라고 부를까요? <span style={{ color: "var(--text-faint)" }}>(선택)</span>
            <Input
              value={nickname}
              onChange={(e) => setNickname(e.target.value.slice(0, 20))}
              placeholder="예: 민수"
              autoComplete="nickname"
              style={{ display: "block", width: "100%", marginTop: "var(--sp-2)", fontWeight: 400 }}
            />
          </label>

          <label
            style={{
              display: "flex",
              gap: "var(--sp-2)",
              alignItems: "flex-start",
              marginTop: "var(--sp-5)",
              fontSize: "var(--fs-sm)",
              color: "var(--text-muted)",
              lineHeight: 1.6,
            }}
          >
            <input
              type="checkbox"
              aria-label="약관 및 개인정보처리방침 동의"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              <Link href="/terms">이용약관</Link> 및 <Link href="/privacy">개인정보처리방침</Link>에 동의하며 만
              14세 이상입니다. 코스와 답변은 생성형 AI가 만들고, 서비스 서버가 일본(Oracle Cloud 오사카)에 있으며
              요청 문장은 미국의 AI 사업자(Anthropic)가 처리해 개인정보가 국외로 이전되는 점, 로그인하지 않은
              체험 기록은 30일 뒤 삭제되는 점에도 동의합니다.
            </span>
          </label>

          {error && (
            <p role="alert" style={{ color: "var(--danger)", fontSize: "var(--fs-sm)", marginTop: "var(--sp-3)" }}>
              {error}
            </p>
          )}

          <Button variant="primary" full onClick={start} disabled={busy} style={{ marginTop: "var(--sp-5)" }}>
            {busy ? "준비 중…" : "시작하기"}
          </Button>
        </div>
      )}

      <p style={{ marginTop: "var(--sp-6)", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
        이미 써 봤나요?{" "}
        <Link href={loginHref} style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
          로그인
        </Link>
      </p>
      <SiteFooter />
    </main>
  );
}
