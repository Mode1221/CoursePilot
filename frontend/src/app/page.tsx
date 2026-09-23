"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import SiteFooter from "@/components/SiteFooter";
import AttributionChips from "@/components/AttributionChips";
import { Button } from "@/components/ui";
import { api } from "@/services/api";
import { toast } from "@/store/toastStore";
import { storedUserId, useUserStore } from "@/store/userStore";

// 랜딩: 가치 제안 + 예시 프롬프트로 바로 시작(예시 클릭 시 해당 조건으로 코스 생성).
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
    setLoading(true);
    try {
      // 첫 렌더 직후 클릭하면 세션 로드가 끝나기 전일 수 있다 → 저장된 id 를 직접 읽는다
      const ownerId = userId ?? storedUserId() ?? undefined;
      const course = await api.createCourse(ownerId);
      const q = seed ? `?seed=${encodeURIComponent(seed)}` : "";
      router.push(`/plan/${course.id}${q}`);
    } catch {
      toast("코스를 만들지 못했어요. 잠시 후 다시 시도해주세요.", "error");
      setLoading(false);
    }
  }

  return (
    <main style={{ padding: "var(--sp-8) var(--sp-4) var(--sp-8)", maxWidth: 560, margin: "0 auto" }}>
      {/* 히어로는 이 제품에서 가장 특징적인 것으로 연다: 두 사람의 답이 하나가 되는 순간 */}
      <h1 style={{ fontSize: "clamp(28px, 8.5vw, 38px)", lineHeight: 1.15, marginTop: "var(--sp-6)", maxWidth: "12em" }}>
        데이트 계획, 검색 말고 상대에게 먼저 물어보세요
      </h1>
      <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-lg)", lineHeight: 1.6, maxWidth: "34ch" }}>
        링크 하나 보내면 상대는 30초. 둘 다 괜찮은 코스가 누구 의견이 어디 들어갔는지까지 보여주며 나와요.
      </p>

      <div style={{ margin: "var(--sp-5) 0 var(--sp-6)" }}>
        <AttributionChips
          label="예시"
          ownerName="민수"
          items={[
            { who: "민수", what: "고기", effect: "저녁 칸" },
            { who: "지은", what: "피곤해", effect: "이동 10분 이내" },
            { who: "지은", what: "매운 거", effect: "매운 거 빼기" },
          ]}
        />
      </div>

      <Button variant="primary" onClick={() => start()} disabled={loading} style={{ minWidth: 200 }}>
        {loading ? "만드는 중…" : "코스 만들고 링크 보내기"}
      </Button>

      {!userId && (
        <p style={{ marginTop: "var(--sp-3)", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          AI에게 조건을 말하려면 가입이 필요해요.{" "}
          <Link href="/onboarding" style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
            30초 가입하기
          </Link>
        </p>
      )}

      <p style={{ marginTop: "var(--sp-12)", marginBottom: "var(--sp-2)", fontSize: "var(--fs-sm)", color: "var(--text-faint)" }}>
        이렇게 시작해도 돼요
      </p>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, borderTop: "1px solid var(--line)" }}>
        {EXAMPLES.map((ex) => (
          <li key={ex.label} style={{ borderBottom: "1px solid var(--border)" }}>
            <button
              onClick={() => start(`${ex.label} ${ex.hint}`)}
              disabled={loading}
              style={{
                width: "100%",
                textAlign: "left",
                background: "none",
                border: "none",
                padding: "var(--sp-4) 0",
                cursor: loading ? "wait" : "pointer",
                color: "inherit",
                font: "inherit",
                display: "grid",
                gap: 2,
              }}
            >
              <span style={{ fontWeight: 600 }}>{ex.label}</span>
              <span style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>{ex.hint}</span>
            </button>
          </li>
        ))}
      </ul>

      <SiteFooter />
    </main>
  );
}
