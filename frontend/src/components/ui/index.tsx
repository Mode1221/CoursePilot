"use client";

import { forwardRef } from "react";
import type { ButtonHTMLAttributes, CSSProperties, InputHTMLAttributes, ReactNode } from "react";

/** 공통 UI 프리미티브. 색·간격은 globals.css 토큰(var(--*))만 사용한다. */

type Variant = "primary" | "soft" | "secondary" | "ghost" | "plain" | "danger";
type Size = "sm" | "md";
// 색·상태(hover/focus/active/disabled)는 globals.css 의 .cp-btn--* 가 담당한다(인라인 색은 hover 를 막는다).

// 최소 터치 타깃 44px(sm 은 36px — 촘촘한 도구 줄에서만 쓴다)
const SIZE: Record<Size, CSSProperties> = {
  sm: { padding: "8px 12px", fontSize: "var(--fs-sm)", minHeight: 36 },
  md: { padding: "12px 18px", fontSize: "var(--fs-md)", minHeight: 44 },
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; full?: boolean }
>(function Button({ variant = "secondary", size = "md", full, style, className, ...rest }, ref) {
  return (
    <button
      ref={ref}
      {...rest}
      className={`cp-btn cp-btn--${variant}${className ? ` ${className}` : ""}`}
      style={{
        ...SIZE[size],
        width: full ? "100%" : undefined,
        borderRadius: "var(--r-full)",
        fontWeight: 600,
        letterSpacing: "-.01em",
        cursor: rest.disabled ? "not-allowed" : "pointer",
        whiteSpace: "nowrap",
        ...style,
      }}
    />
  );
});

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ style, ...rest }, ref) {
  return (
    <input
      ref={ref}
      {...rest}
      style={{
        padding: "10px 12px",
        fontSize: "var(--fs-md)",
        color: "var(--text)",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-md)",
        outline: "none",
        ...style,
      }}
    />
  );
},
);

export function Card({ children, style, interactive }: { children: ReactNode; style?: CSSProperties; interactive?: boolean }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-lg)",
        padding: "var(--sp-4)",
        boxShadow: "var(--shadow-1)",
        transition: interactive ? "box-shadow var(--dur) var(--ease)" : undefined,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "brand" | "warn" | "owner" | "partner";
}) {
  const tones = {
    neutral: { background: "var(--surface-2)", color: "var(--text-muted)" },
    brand: { background: "var(--brand-weak)", color: "var(--brand-strong)" },
    warn: { background: "var(--surface-2)", color: "var(--warn)" },
    owner: { background: "var(--owner-weak)", color: "var(--owner)" },
    partner: { background: "var(--partner-weak)", color: "var(--partner)" },
  } as const;
  return (
    <span
      style={{
        ...tones[tone],
        padding: "3px 9px",
        borderRadius: "var(--r-full)",
        fontSize: "var(--fs-xs)",
        fontWeight: 600,
        whiteSpace: "nowrap",
        lineHeight: 1.4,
      }}
    >
      {children}
    </span>
  );
}

export function Skeleton({ height = 16, width = "100%", style }: { height?: number | string; width?: number | string; style?: CSSProperties }) {
  return <div className="cp-skeleton" style={{ height, width, ...style }} aria-hidden />;
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div style={{ textAlign: "center", padding: "var(--sp-8) var(--sp-4)", color: "var(--text-muted)" }}>
      <p style={{ fontWeight: 600, color: "var(--text)", marginBottom: "var(--sp-1)" }}>{title}</p>
      {description && <p style={{ fontSize: "var(--fs-sm)" }}>{description}</p>}
      {action}
    </div>
  );
}
