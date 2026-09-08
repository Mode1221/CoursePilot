"use client";

import { useEffect } from "react";

import { useToastStore } from "@/store/toastStore";

const TONE_STYLE: Record<string, { bg: string; fg: string }> = {
  info: { bg: "var(--surface-2)", fg: "var(--text)" },
  error: { bg: "var(--danger)", fg: "#fff" },
  success: { bg: "var(--brand)", fg: "var(--brand-contrast)" },
};

const TTL_MS = 4000;

function ToastItem({ id, text, tone }: { id: number; text: string; tone: string }) {
  const dismiss = useToastStore((s) => s.dismiss);
  useEffect(() => {
    const t = setTimeout(() => dismiss(id), TTL_MS);
    return () => clearTimeout(t);
  }, [id, dismiss]);

  const style = TONE_STYLE[tone] ?? TONE_STYLE.info;
  return (
    <div
      className="cp-enter"
      style={{
        background: style.bg,
        color: style.fg,
        border: "1px solid var(--border)",
        borderRadius: "var(--r-md)",
        boxShadow: "var(--shadow-2)",
        padding: "var(--sp-3) var(--sp-4)",
        fontSize: "var(--fs-sm)",
        cursor: "pointer",
      }}
      onClick={() => dismiss(id)}
    >
      {text}
    </div>
  );
}

/** 화면 하단 중앙 토스트. 스크린리더에는 aria-live 로 전달. */
export default function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        left: "50%",
        bottom: "var(--sp-6)",
        transform: "translateX(-50%)",
        display: "grid",
        gap: "var(--sp-2)",
        zIndex: 50,
        maxWidth: "min(90vw, 420px)",
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} id={t.id} text={t.text} tone={t.tone} />
      ))}
    </div>
  );
}
