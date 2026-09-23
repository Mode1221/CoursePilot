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
  // 칩이 "👤지은 피곤해"처럼 이름으로 나와야 "내 말 들었네"가 된다 — 나/상대로는 약하다
  const [ownerName, setOwnerName] = useState("");
  const [partnerName, setPartnerName] = useState("");
  const [status, setStatus] = useState<TogetherStatus | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);

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

  // 소켓이 끊겨도 상대가 냈는지 알 수 있게, 기다리는 동안은 가볍게 확인한다
  const waiting = !!status && !status.submitted.some((n) => n !== status.owner_name);
  useEffect(() => {
    if (!waiting) return;
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [waiting, refresh]);

  if (!userId) return null;

  const link = token && typeof window !== "undefined" ? `${window.location.origin}/together/${token}` : null;
  const mySent = status?.submitted.includes(status.owner_name) ?? false;
  const partnerSent = status ? status.submitted.some((n) => n !== status.owner_name) : false;
  const accepted = course?.together?.accepted_by ?? [];

  async function start() {
    if (!text.trim()) return toast("언제 어디서 볼지 한 줄만 적어 주세요. 예: 토요일 3시 성수", "error");
    if (!ownerName.trim() || !partnerName.trim()) return toast("내 이름과 상대 이름을 적어 주세요. 칩에 이름으로 보여요.", "error");
    if (ownerName.trim() === partnerName.trim()) return toast("두 이름이 같아요. 구분되게 적어 주세요.", "error");
    setBusy(true);
    try {
      await api.togetherStart(courseId, userId!, {
        text: text.trim(),
        owner_name: ownerName.trim(),
        partner_name: partnerName.trim(),
      });
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
        <h3 style={{ margin: "0 0 var(--sp-1)", fontSize: "var(--fs-lg)" }}>상대에게 먼저 물어보기</h3>
        <p style={{ margin: "0 0 var(--sp-4)", color: "var(--text-muted)", fontSize: "var(--fs-sm)", lineHeight: 1.5 }}>
          링크를 보내면 상대가 30초 카드에 답해요. 둘의 답을 합쳐 코스를 만듭니다.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "var(--sp-2)", marginBottom: "var(--sp-2)" }}>
          <input
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
            placeholder="내 이름 (예: 민수)"
            aria-label="내 이름"
            maxLength={10}
            style={{ minWidth: 0, padding: "12px 14px", border: "1.5px solid var(--line)", borderRadius: "var(--r-md)", font: "inherit", background: "var(--surface)" }}
          />
          <input
            value={partnerName}
            onChange={(e) => setPartnerName(e.target.value)}
            placeholder="상대 이름 (예: 지은)"
            aria-label="상대 이름"
            maxLength={10}
            style={{ minWidth: 0, padding: "12px 14px", border: "1.5px solid var(--line)", borderRadius: "var(--r-md)", font: "inherit", background: "var(--surface)" }}
          />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "var(--sp-2)" }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="언제 어디서 · 예: 토요일 3시 성수…"
            aria-label="언제 어디서"
            style={{ minWidth: 0, padding: "12px 14px", border: "1.5px solid var(--line)", borderRadius: "var(--r-md)", font: "inherit", background: "var(--surface)" }}
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
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: "var(--sp-2)",
          background: "none",
          border: 0,
          padding: 0,
          font: "inherit",
          color: "inherit",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span style={{ flex: 1, minWidth: 0, display: "grid", gap: 6 }}>
          <span style={{ fontWeight: 700, fontSize: "var(--fs-md)" }}>
            {status.owner_name}·{status.partner_name} 같이 정하는 중
          </span>
          <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Badge tone={mySent ? "owner" : "neutral"}>{mySent ? `${status.owner_name} 카드 ✓` : `${status.owner_name} 카드 전`}</Badge>
            <Badge tone={partnerSent ? "partner" : "neutral"}>{partnerSent ? `${status.partner_name} 답함` : `${status.partner_name} 기다리는 중`}</Badge>
          </span>
        </span>
        <span aria-hidden="true" style={{ color: "var(--text-faint)", fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div style={{ display: "grid", gap: "var(--sp-4)", marginTop: "var(--sp-4)" }}>
          <div style={{ display: "flex", gap: "var(--sp-2)", alignItems: "center", flexWrap: "wrap" }}>
            <code style={{ fontSize: "var(--fs-xs)", color: "var(--text-muted)", wordBreak: "break-all" }}>{link}</code>
            <Button size="sm" variant="soft" onClick={copy}>링크 복사</Button>
          </div>
          {(!mySent || editing) && (
            <TogetherCards
              spec={status.cards}
              submitLabel={editing ? "수정한 카드 저장" : "내 카드 저장"}
              storageKey={`coursepilot_together_card:owner:${courseId}`}
              onSubmit={async (card) => {
                try {
                  setStatus(await api.togetherOwnerInput(courseId, userId!, { ...card, name: status.owner_name }));
                  setEditing(false);
                } catch {
                  toast("저장하지 못했어요.", "error");
                }
              }}
            />
          )}
          {mySent && !editing && (
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)} style={{ justifySelf: "start" }}>
              내 카드 수정
            </Button>
          )}
          {(status.stale || course?.together?.stale) && (
            <p role="status" style={{ margin: 0, color: "var(--warn)", fontSize: "var(--fs-sm)" }}>
              카드가 바뀌었어요. 다시 합치면 새 답으로 코스를 만들어요.
            </p>
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
  borderRadius: "var(--r-lg)",
  background: "var(--surface)",
  boxShadow: "var(--shadow-1)",
  marginBottom: "var(--sp-3)",
} as const;
