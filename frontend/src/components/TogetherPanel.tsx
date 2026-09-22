"use client";

import { useCallback, useEffect, useState } from "react";

import TogetherCards from "@/components/TogetherCards";
import { Badge, Button } from "@/components/ui";
import { api, type TogetherStatus } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

/**
 * 시작하는 사람의 "먼저 상대에게 묻기" 패널.
 * 한 줄 요청 → 링크 복사 → 내 카드 → (상대가 내면) 합치기 → 반영 칩이 붙은 코스 → 수락.
 */
export default function TogetherPanel({ courseId }: { courseId: string }) {
  const { userId } = useUserStore();
  const course = useCourseStore((s) => s.course);
  const setCourse = useCourseStore((s) => s.setCourse);
  const [text, setText] = useState("");
  const [status, setStatus] = useState<TogetherStatus | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const { token } = await api.togetherLink(courseId, userId);
      setToken(token);
      setStatus(await api.togetherStatus(token));
    } catch {
      /* 아직 시작 전 */
    }
  }, [courseId, userId]);

  useEffect(() => {
    if (course?.together) refresh();
  }, [course?.together, refresh]);

  if (!userId) return null;

  const link = token && typeof window !== "undefined" ? `${window.location.origin}/together/${token}` : null;
  const mySent = status?.submitted.includes(status.owner_name) ?? false;
  const partnerSent = status ? status.submitted.some((n) => n !== status.owner_name) : false;
  const accepted = course?.together?.accepted_by ?? [];

  async function start() {
    if (!text.trim()) return toast("언제 어디서 볼지 한 줄만 적어 주세요. 예: 토요일 3시 성수", "error");
    setBusy(true);
    try {
      await api.togetherStart(courseId, userId!, { text: text.trim() });
      await refresh();
      setOpen(true);
    } catch {
      toast("시작하지 못했어요.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(`${status?.request_text ?? ""} 같이 정하자! 30초면 돼 → ${link}`);
      toast("링크를 복사했어요. 카톡에 붙여넣어 보내세요.", "success");
    } catch {
      toast("복사하지 못했어요.", "error");
    }
  }

  async function build() {
    setBusy(true);
    try {
      const r = await api.togetherBuild(courseId, userId!);
      setCourse(r.course);
      setStatus(r.status);
    } catch {
      toast("코스를 만들지 못했어요.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    try {
      const s = await api.togetherOwnerAccept(courseId, userId!);
      setStatus(s);
      toast(s.accepted_by.length >= 2 ? "둘 다 좋아요! 코스 확정 🎉" : "수락했어요. 상대 답을 기다릴게요.", "success");
    } catch {
      toast("수락하지 못했어요.", "error");
    }
  }

  // 아직 시작 전
  if (!status) {
    return (
      <section style={box}>
        <h3 style={{ margin: "0 0 var(--sp-1)" }}>검색 말고, 상대에게 먼저 물어보기</h3>
        <p style={{ margin: "0 0 var(--sp-3)", color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
          링크를 보내면 상대가 30초 카드에 답해요. 둘 다 괜찮은 코스가 나옵니다.
        </p>
        <div style={{ display: "flex", gap: "var(--sp-2)" }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="토요일 3시 성수"
            aria-label="언제 어디서"
            style={{ flex: 1, padding: "var(--sp-2) var(--sp-3)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", font: "inherit" }}
          />
          <Button variant="primary" onClick={start} disabled={busy}>
            링크 만들기
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section style={box}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", marginBottom: "var(--sp-2)" }}>
        <h3 style={{ margin: 0 }}>같이 정하기</h3>
        <Badge tone={partnerSent ? "brand" : "neutral"}>{partnerSent ? `${status.partner_name} 답함` : "상대 기다리는 중"}</Badge>
        <Badge tone={mySent ? "brand" : "neutral"}>{mySent ? "내 카드 완료" : "내 카드 전"}</Badge>
        <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)} style={{ marginLeft: "auto" }}>
          {open ? "접기" : "펼치기"}
        </Button>
      </div>
      {open && (
        <div style={{ display: "grid", gap: "var(--sp-4)" }}>
          <div style={{ display: "flex", gap: "var(--sp-2)", alignItems: "center", flexWrap: "wrap" }}>
            <code style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)", wordBreak: "break-all" }}>{link}</code>
            <Button size="sm" onClick={copy}>링크 복사</Button>
          </div>
          {!mySent && (
            <TogetherCards
              spec={status.cards}
              submitLabel="내 카드 저장"
              onSubmit={async (card) => {
                try {
                  setStatus(await api.togetherOwnerInput(courseId, userId!, { ...card, name: status.owner_name }));
                } catch {
                  toast("저장하지 못했어요.", "error");
                }
              }}
            />
          )}
          <div style={{ display: "flex", gap: "var(--sp-2)", flexWrap: "wrap" }}>
            <Button variant="primary" onClick={build} disabled={busy || status.submitted.length === 0}>
              {busy ? "합치는 중…" : status.built ? "다시 합치기" : partnerSent && mySent ? "둘의 카드 합쳐서 코스 만들기" : "일단 내 기준으로 초안 만들기"}
            </Button>
            {status.built && (
              <Button onClick={accept} disabled={accepted.includes(status.owner_name)}>
                {accepted.includes(status.owner_name) ? "수락함" : "이 코스 좋아요"}
              </Button>
            )}
          </div>
          {course?.together?.conflict_note && (
            <p style={{ margin: 0, fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
              {course.together.conflict_note}
              {course.together.yielded && ` · 이번엔 ${course.together.yielded}님이 양보했어요`}
            </p>
          )}
          {accepted.length >= 2 && <Badge tone="brand">둘 다 좋아요 · 확정</Badge>}
        </div>
      )}
    </section>
  );
}

const box = {
  padding: "var(--sp-4)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)",
  background: "var(--surface)",
  marginBottom: "var(--sp-3)",
} as const;
