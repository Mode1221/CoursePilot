"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import TogetherCards from "@/components/TogetherCards";
import { Button, Skeleton } from "@/components/ui";
import { api, ApiError, type TogetherStatus } from "@/services/api";
import { saveTogetherToken } from "@/services/togetherToken";
import { toast } from "@/store/toastStore";

/**
 * 상대가 링크로 들어오는 화면. 가입 없음, 30초, 서로의 답은 안 보인다.
 * 카드를 내면 "합쳐볼게요"로 넘어가고, 코스가 만들어지면 공유 화면으로 보낸다.
 */
export default function TogetherPage({ params }: { params: { token: string } }) {
  const { token } = params;
  const [status, setStatus] = useState<TogetherStatus | null>(null);
  const [missing, setMissing] = useState(false);
  const [sent, setSent] = useState(false);
  const [myName, setMyName] = useState("");

  const load = useCallback(async () => {
    try {
      const s = await api.togetherStatus(token);
      setStatus(s);
      setMyName((n) => n || s.partner_name);
      saveTogetherToken(s.course_id, token);
      // 코스 화면의 "내 카드 수정"(?edit=1)으로 왔으면 이미 냈어도 카드를 바로 연다
      const editing = new URLSearchParams(window.location.search).has("edit");
      setSent((prev) => (editing && !prev ? false : prev || s.submitted.includes(s.partner_name)));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setMissing(true);
      else toast("상태를 불러오지 못했어요.", "error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  // 보낸 뒤엔 코스가 만들어졌는지 가볍게 확인한다(소켓 없이도 동작)
  useEffect(() => {
    if (!sent || status?.built) return;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [sent, status?.built, load]);

  if (missing) {
    return (
      <main style={wrap}>
        <h1>링크가 만료됐거나 잘못됐어요</h1>
        <p style={{ color: "var(--text-muted)" }}>보낸 사람에게 새 링크를 부탁해 주세요.</p>
        <Link href="/">처음으로</Link>
      </main>
    );
  }
  if (!status) {
    return (
      <main style={wrap}>
        <Skeleton height={28} width="60%" />
        <Skeleton height={120} style={{ marginTop: "var(--sp-4)" }} />
      </main>
    );
  }

  if (sent) {
    return (
      <main style={wrap}>
        <h1>보냈어요 ✨</h1>
        <p style={{ color: "var(--text-muted)" }}>
          {status.owner_name}님 답이랑 합쳐볼게요. {status.built ? "코스가 준비됐어요!" : "잠깐만 기다려 주세요."}
        </p>
        {status.built && (
          <Link href={`/plan/${status.course_id}`}>
            <Button variant="primary" full>코스 보러 가기</Button>
          </Link>
        )}
        <Button full variant="ghost" onClick={() => setSent(false)} style={{ marginTop: "var(--sp-2)" }}>
          내 답 수정하기
        </Button>
        <p style={{ marginTop: "var(--sp-6)", fontSize: "var(--fs-xs)", color: "var(--text-faint)" }}>
          내 답은 합친 뒤에도 예산은 공개되지 않아요.
        </p>
      </main>
    );
  }

  return (
    <main style={wrap}>
      <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
        {status.owner_name}님이 같이 정하재요 · 30초 · 가입 없음
      </p>
      <h1 style={{ marginTop: "var(--sp-1)" }}>{status.request_text}</h1>
      <p style={{ color: "var(--text-muted)", marginBottom: "var(--sp-3)" }}>
        탭만 하면 돼요. 서로의 답은 합치기 전까지 안 보여요.
      </p>
      <label style={{ display: "block", marginBottom: "var(--sp-5)", fontSize: "var(--fs-sm)" }}>
        내 이름{" "}
        <input
          value={myName}
          onChange={(e) => setMyName(e.target.value)}
          maxLength={10}
          aria-label="내 이름"
          style={{ marginLeft: "var(--sp-2)", padding: "6px 10px", border: "1px solid var(--border)", borderRadius: "var(--r-md)", font: "inherit" }}
        />
      </label>
      <TogetherCards
        spec={status.cards}
        storageKey={`coursepilot_together_card:${token}`}
        submitLabel={status.submitted.includes(status.partner_name) ? "수정한 답 보내기" : "보냈어요"}
        onSubmit={async (card) => {
          try {
            const name = myName.trim() || status.partner_name;
            const s = await api.togetherPartnerInput(token, { ...card, name });
            setStatus(s);
            setSent(true);
          } catch {
            toast("보내지 못했어요. 다시 시도해 주세요.", "error");
          }
        }}
      />
    </main>
  );
}

const wrap = { padding: "var(--sp-8) var(--sp-4)", maxWidth: 520, margin: "0 auto" } as const;
