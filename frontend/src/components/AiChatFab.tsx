"use client";

import { useEffect, useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import { useCourseStore } from "@/store/courseStore";

/**
 * AI 채팅 — 떠 있는 버튼. 누르면 넓은 화면은 오른쪽 아래 패널, 좁은 화면은 아래에서 올라오는 시트.
 * 채팅은 가끔 쓰는 도구라 코스 화면의 자리를 상시 차지하지 않게 했다.
 */
export default function AiChatFab({ courseId, narrow }: { courseId: string; narrow: boolean }) {
  const [open, setOpen] = useState(false);
  // 넓은 화면은 지도 쪽(왼쪽)에 띄운다 — 오른쪽은 타임라인이라 패널이 교체·삭제 버튼을 가렸다(E2E 로 발견)
  const side = narrow ? { right: 20 } : { left: 20 };
  // 휴대폰: AI 가 코스를 바꾸면 시트를 내려 결과가 바로 보이게
  const itemsKey = useCourseStore((s) => (s.course?.items ?? []).map((it) => it.place.id).join(","));
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  useEffect(() => {
    if (open) setOpenedAt((k) => k ?? itemsKey);
    else setOpenedAt(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  useEffect(() => {
    if (narrow && open && openedAt !== null && itemsKey !== openedAt && itemsKey !== "") setOpen(false);
  }, [narrow, open, openedAt, itemsKey]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="AI에게 말하기"
          style={{
            position: "fixed",
            ...side,
            // 넓은 화면: 지도 아래 AI 고지 문구를 가리지 않게 조금 더 위
            bottom: narrow ? `calc(76px + env(safe-area-inset-bottom, 0px))` : 104,
            zIndex: 1500,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "14px 18px",
            borderRadius: "var(--r-full)",
            border: 0,
            background: "var(--text)",
            color: "var(--bg)",
            fontWeight: 700,
            fontSize: "var(--fs-md)",
            boxShadow: "var(--shadow-2)",
            cursor: "pointer",
          }}
        >
          <span aria-hidden="true">✦</span> AI에게 말하기
        </button>
      )}
      {open && (
        <>
          {narrow && (
            <div
              aria-hidden="true"
              onClick={() => setOpen(false)}
              style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.35)", zIndex: 1550 }}
            />
          )}
          <section
            role="dialog"
            aria-label="AI 챗봇"
            className="cp-enter"
            style={{
              position: "fixed",
              zIndex: 1600,
              background: "var(--surface)",
              boxShadow: "var(--shadow-2)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              ...(narrow
                ? { left: 0, right: 0, bottom: 0, height: "82dvh", borderRadius: "16px 16px 0 0" }
                : { left: 20, bottom: 76, width: 420, height: "min(600px, calc(100dvh - 160px))", borderRadius: 16 }),
            }}
          >
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="채팅 닫기"
              style={{
                position: "absolute",
                top: 10,
                right: 12,
                zIndex: 2,
                width: 32,
                height: 32,
                borderRadius: "50%",
                border: 0,
                background: "var(--surface-2)",
                cursor: "pointer",
                fontSize: 16,
              }}
            >
              ✕
            </button>
            <ChatPanel courseId={courseId} compact />
          </section>
        </>
      )}
    </>
  );
}
