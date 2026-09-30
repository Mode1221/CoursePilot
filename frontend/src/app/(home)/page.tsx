"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import SiteFooter from "@/components/SiteFooter";
import AttributionChips from "@/components/AttributionChips";
import { BrandMark, Button } from "@/components/ui";
import { createCourseUrl } from "@/services/newCourse";
import { NEW_COURSE } from "@/services/nextPath";
import { storedUserId, useUserStore } from "@/store/userStore";

// 랜딩: 가치 제안 + 예시 프롬프트로 바로 시작. 처음 온 사람은 가입 없이 체험으로 시작한다.
const EXAMPLES = [
  { label: "토요일 3시 성수", hint: "둘이 5만원 · 도보 10분 이내" },
  { label: "○○카페 들렀다가 저녁까지", hint: "정해둔 한 곳 기준으로 앞뒤 채우기" },
  { label: "비 오는 토요일 홍대", hint: "실내 위주 · 두 군데" },
  { label: "일요일 연남동 브런치", hint: "오전 11시 시작" },
];

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const { userId, load } = useUserStore();

  useEffect(() => {
    load();
  }, [load]);

  async function start(seed?: string) {
    // 첫 렌더 직후 클릭하면 세션 로드가 끝나기 전일 수 있다 → 저장된 id 를 직접 읽는다
    if (!(userId ?? storedUserId())) {
      const q = seed ? `&seed=${encodeURIComponent(seed)}` : "";
      router.push(`/start?next=${NEW_COURSE}${q}`);
      return;
    }
    setLoading(true);
    const url = await createCourseUrl(seed);
    if (url) router.push(url);
    else setLoading(false);
  }

  return (
    <main style={{ padding: "var(--sp-5) var(--sp-4) var(--sp-8)", maxWidth: 1040, margin: "0 auto" }}>
      <header className="cp-rise" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Link href="/" className="cp-logo" aria-label="픽앤어스 처음으로">
          <BrandMark size={30} decorative />
          픽앤어스
        </Link>
        <Link href="/mypage" className="cp-nav__link">
          내 코스
        </Link>
      </header>

      <div className="cp-hero">
      <section>
      {/* 히어로는 이 제품에서 가장 특징적인 것으로 연다: 두 사람의 답이 하나가 되는 순간 */}
      <p className="cp-eyebrow cp-rise" style={{ ["--i" as string]: 1, marginTop: "var(--sp-8)", marginBottom: "var(--sp-3)" }}>
        둘이 같이 정하는 데이트 코스
      </p>
      <h1
        className="cp-rise"
        style={{ ["--i" as string]: 2, fontSize: "clamp(34px, 9.5vw, 58px)", lineHeight: 1.18, letterSpacing: "-.035em", maxWidth: "11em" }}
      >
        데이트 계획, 검색 말고 <span className="cp-mark-hl">상대에게 먼저</span> 물어보세요
      </h1>
      <p className="cp-rise" style={{ ["--i" as string]: 3, color: "var(--text-muted)", fontSize: "var(--fs-lg)", lineHeight: 1.65, maxWidth: "34ch" }}>
        링크 하나 보내면 상대는 30초. 둘 다 괜찮은 코스가 누구 의견이 어디 들어갔는지까지 보여주며 나와요.
      </p>

      <div className="cp-rise" style={{ ["--i" as string]: 4, marginTop: "var(--sp-6)" }}>
      <Button variant="primary" onClick={() => start()} disabled={loading} style={{ minWidth: 220, minHeight: 52, fontSize: "var(--fs-lg)" }}>
        {loading ? "만드는 중…" : "코스 만들고 링크 보내기"}
      </Button>

      {!userId && (
        <p style={{ marginTop: "var(--sp-3)", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          가입 없이 한 번 써 볼 수 있어요. 이미 써 봤다면{" "}
          <Link href="/login" style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
            로그인
          </Link>
        </p>
      )}
      </div>
      </section>

      <div className="cp-letter cp-rise" style={{ ["--i" as string]: 5 }}>
        <div className="cp-letter__bubbles" aria-hidden>
          <span className="cp-bubble cp-bubble--owner cp-float">민수 · 고기 먹고 싶어</span>
          <span className="cp-bubble cp-bubble--partner cp-float" style={{ animationDelay: "-2.5s" }}>
            지은 · 오늘 좀 피곤해
          </span>
        </div>
        <AttributionChips
          label="예시"
          ownerName="민수"
          items={[
            { who: "민수", what: "고기", effect: "저녁 칸" },
            { who: "지은", what: "피곤해", effect: "이동 10분 이내" },
            { who: "지은", what: "매운 거", effect: "매운 거 빼기" },
          ]}
        />
        <p className="cp-letter__foot">둘의 말이 코스 어디에 들어갔는지 보여줘요</p>
      </div>
      </div>

      <h2
        className="cp-rise"
        style={{ ["--i" as string]: 6, marginTop: "var(--sp-12)", marginBottom: "var(--sp-3)", fontSize: "var(--fs-xl)" }}
      >
        이렇게 시작해도 돼요
      </h2>
      <ul className="cp-examples">
        {EXAMPLES.map((ex, i) => (
          <li key={ex.label} className="cp-rise" style={{ ["--i" as string]: 7 + i }}>
            <button
              className="cp-example"
              onClick={() => start(`${ex.label} ${ex.hint}`)}
              disabled={loading}
              style={{ cursor: loading ? "wait" : "pointer" }}
            >
              <span style={{ fontWeight: 700 }}>{ex.label}</span>
              <span style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>{ex.hint}</span>
              <span className="cp-example__go" aria-hidden>→</span>
            </button>
          </li>
        ))}
      </ul>

      <SiteFooter />
    </main>
  );
}
