"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import BrandMark from "@/components/BrandMark";
import SiteFooter from "@/components/SiteFooter";
import { Button } from "@/components/ui";
import { createCourseUrl } from "@/services/newCourse";
import { NEW_COURSE } from "@/services/nextPath";
import { storedUserId, useUserStore } from "@/store/userStore";

// 랜딩: 가치 제안 + 예시 프롬프트로 바로 시작. 처음 온 사람은 가입 없이 체험으로 시작한다.
const EXAMPLES = [
  { label: "토요일 3시 성수", hint: "둘이 5만원, 도보 10분 이내" },
  { label: "○○카페 들렀다가 저녁까지", hint: "정해둔 한 곳 기준으로 앞뒤 채우기" },
  { label: "비 오는 토요일 홍대", hint: "실내 위주로 두 군데" },
  { label: "일요일 연남동 브런치", hint: "오전 11시 시작" },
];

const STEPS = [
  { title: "내가 먼저 적어요", body: "언제, 어디서, 대충 뭘 하고 싶은지. 한 줄이면 돼요." },
  { title: "링크를 보내요", body: "상대는 가입 없이 30초. 먹고 싶은 것, 피하고 싶은 것만 골라요." },
  { title: "둘의 답이 코스가 돼요", body: "누구 의견이 어느 칸에 들어갔는지 보이니까 서로 설명할 필요가 없어요." },
];

/** 연출 순서(ms) — 데모 한 장에서만 움직인다 */
const at = (ms: number) => ({ "--step": ms }) as CSSProperties;

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
    <>
      <header className="cp-topbar" style={{ position: "static", background: "transparent", borderBottom: 0 }}>
        <BrandMark />
        <nav aria-label="주 메뉴" style={{ marginLeft: "auto", display: "flex", gap: 2 }}>
          <Link href="/mypage" className="cp-topbar__link">
            내 코스
          </Link>
          {!userId && (
            <Link href="/login" className="cp-topbar__link cp-topbar__link--strong">
              로그인
            </Link>
          )}
        </nav>
      </header>

      <main className="cp-home">
        {/* 히어로는 이 제품에서 가장 특징적인 것으로 연다: 두 사람의 답이 하나가 되는 순간 */}
        <section className="cp-home__hero">
          <div>
            <h1 className="cp-home__title">데이트 계획, 검색 말고 상대에게 먼저 물어보세요</h1>
            <p className="cp-home__lead">
              링크 하나 보내면 상대는 30초. 둘 다 괜찮은 코스가 누구 의견이 어디 들어갔는지까지 보여주며 나와요.
            </p>
            <div className="cp-home__cta">
              <Button variant="primary" onClick={() => start()} disabled={loading}>
                {loading ? "만드는 중…" : "코스 만들고 링크 보내기"}
              </Button>
              {!userId && (
                <p style={{ margin: 0, fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
                  가입 없이 한 번 써 볼 수 있어요. 이미 써 봤다면{" "}
                  <Link href="/login" style={{ fontWeight: 600 }}>
                    로그인
                  </Link>
                </p>
              )}
            </div>
          </div>

          <MergeDemo />
        </section>

        <section className="cp-home__section" aria-labelledby="how">
          <h2 id="how">이렇게 정해져요</h2>
          <ol className="cp-steps">
            {STEPS.map((s) => (
              <li key={s.title} className="cp-step">
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="cp-home__section" aria-labelledby="examples">
          <h2 id="examples">이렇게 시작해도 돼요</h2>
          <ul className="cp-rows">
            {EXAMPLES.map((ex) => (
              <li key={ex.label}>
                <button className="cp-row" onClick={() => start(`${ex.label} ${ex.hint}`)} disabled={loading}>
                  <span className="cp-row__title">{ex.label}</span>
                  <span className="cp-row__sub">{ex.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <SiteFooter />
      </main>
    </>
  );
}

/** 예시 장면: 민수와 지은의 답 → 두 선이 모여 → 하나의 코스(칸마다 누구 의견인지) */
function MergeDemo() {
  return (
    <figure className="cp-demo" aria-label="예시: 두 사람의 답이 하나의 코스가 되는 모습">
      <div className="cp-demo__answers">
        <p className="cp-bubble cp-bubble--owner" data-step style={at(100)}>
          <span className="cp-bubble__who">민수</span>
          토요일 성수 어때? 저녁은 고기 먹고 싶어
        </p>
        <p className="cp-bubble cp-bubble--partner" data-step style={at(420)}>
          <span className="cp-bubble__who">지은</span>
          좋아! 대신 오늘 좀 피곤해. 매운 건 빼 줘
        </p>
      </div>

      <svg className="cp-demo__merge" viewBox="0 0 300 56" aria-hidden="true">
        <path d="M60 0 C60 34 150 22 150 56" pathLength={1} style={{ stroke: "var(--owner)" }} />
        <path d="M240 0 C240 34 150 22 150 56" pathLength={1} style={{ stroke: "var(--partner)" }} />
      </svg>
      <p className="cp-demo__caption" data-step style={at(1150)}>
        둘 다 괜찮은 코스
      </p>

      <ol className="cp-rail">
        <DemoStop n={1} place="성수 브런치 카페" time="15:00" step={1300} chips={[["지은", "partner", "이동 10분 이내"]]} />
        <DemoStop n={2} place="소품샵 골목 산책" time="16:30" step={1450} chips={[["지은", "partner", "걷는 건 짧게"]]} />
        <DemoStop
          n={3}
          place="숯불 고깃집"
          time="18:30"
          step={1600}
          chips={[
            ["민수", "owner", "고기"],
            ["지은", "partner", "매운 거 빼기"],
          ]}
        />
      </ol>
    </figure>
  );
}

function DemoStop({
  n,
  place,
  time,
  step,
  chips,
}: {
  n: number;
  place: string;
  time: string;
  step: number;
  chips: [who: string, role: "owner" | "partner", what: string][];
}) {
  return (
    <li className="cp-stop" data-step style={at(step)}>
      <span className="cp-stop__n" aria-hidden="true">
        {n}
      </span>
      <span className="cp-demo__place">{place}</span>
      <span className="cp-demo__time">{time}</span>
      <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {chips.map(([who, role, what]) => (
          <span key={what} className={`cp-person cp-person--${role}`}>
            <span className="cp-person__avatar" aria-hidden="true">
              {who.slice(0, 1)}
            </span>
            <span className="sr-only">{who} 의견: </span>
            {what}
          </span>
        ))}
      </span>
    </li>
  );
}
