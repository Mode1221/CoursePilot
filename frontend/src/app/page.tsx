"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import SiteFooter from "@/components/SiteFooter";
import { Button, Card } from "@/components/ui";
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
    <main style={{ padding: "var(--sp-12) var(--sp-4)", maxWidth: 620, margin: "0 auto" }}>
      <div
        style={{
          display: "inline-block",
          background: "var(--brand-weak)",
          color: "var(--brand-strong)",
          padding: "4px 12px",
          borderRadius: "var(--r-full)",
          fontSize: "var(--fs-xs)",
          fontWeight: 700,
          marginBottom: "var(--sp-4)",
        }}
      >
        둘이 같이 정하는 데이트 코스
      </div>

      <h1>데이트 계획, 검색 말고 상대에게 먼저 물어보세요</h1>
      <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-lg)" }}>
        링크 하나 보내면 상대는 30초. 둘 다 괜찮은 코스가 누구 의견이 어디 들어갔는지까지 보여주며 나와요.
        영업시간·폐업·동선은 기본으로 확인합니다.
      </p>

      <Button variant="primary" onClick={() => start()} disabled={loading} style={{ marginTop: "var(--sp-4)" }}>
        {loading ? "생성 중…" : "새 코스 시작"}
      </Button>

      {!userId && (
        <p style={{ marginTop: "var(--sp-3)", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          AI에게 조건을 말하려면 가입이 필요해요.{" "}
          <Link href="/onboarding" style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
            30초 가입하기
          </Link>
        </p>
      )}

      <h4 style={{ marginTop: "var(--sp-8)" }}>이런 코스는 어때요?</h4>
      <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "var(--sp-2)" }}>
        {EXAMPLES.map((ex) => (
          <li key={ex.label}>
            <Card interactive style={{ padding: 0 }}>
              <button
                onClick={() => start(`${ex.label} ${ex.hint}`)}
                disabled={loading}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: "none",
                  border: "none",
                  padding: "var(--sp-3) var(--sp-4)",
                  cursor: loading ? "wait" : "pointer",
                  color: "inherit",
                  font: "inherit",
                }}
              >
                <div style={{ fontWeight: 600 }}>{ex.label}</div>
                <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>{ex.hint}</div>
              </button>
            </Card>
          </li>
        ))}
      </ul>

      <SiteFooter />
    </main>
  );
}
