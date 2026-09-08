"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card } from "@/components/ui";
import { api } from "@/services/api";
import { useUserStore } from "@/store/userStore";

// 랜딩: 가치 제안 + 예시 프롬프트로 바로 시작(예시 클릭 시 해당 조건으로 코스 생성).
const EXAMPLES = [
  { label: "토요일 오후 성수동 데이트", hint: "3시간 · 도보 10분 이내" },
  { label: "금요일 저녁 강남역 회식", hint: "4명 · 1인 3만원" },
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
      const course = await api.createCourse(userId ?? undefined);
      const q = seed ? `?seed=${encodeURIComponent(seed)}` : "";
      router.push(`/plan/${course.id}${q}`);
    } finally {
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
        영업시간 · 이동시간까지 검증
      </div>

      <h1>말만 하면, 실제로 갈 수 있는 코스</h1>
      <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-lg)" }}>
        조건을 자연어로 입력하면 문 닫은 곳·무리한 동선을 걸러낸 모임 코스를 만들어 드려요.
      </p>

      <Button variant="primary" onClick={() => start()} disabled={loading} style={{ marginTop: "var(--sp-4)" }}>
        {loading ? "생성 중…" : "새 코스 시작"}
      </Button>

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

      <p style={{ marginTop: "var(--sp-8)", fontSize: "var(--fs-sm)", color: "var(--text-faint)" }}>
        <Link href="/onboarding" style={{ color: "var(--text-muted)" }}>선호 설정</Link>
        {" · "}
        <Link href="/mypage" style={{ color: "var(--text-muted)" }}>내 코스</Link>
      </p>
    </main>
  );
}
