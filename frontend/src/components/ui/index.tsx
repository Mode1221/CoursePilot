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
      className={`cp-input${rest.className ? ` ${rest.className}` : ""}`}
      style={{
        padding: "12px 14px",
        fontSize: "var(--fs-md)",
        color: "var(--text)",
        background: "var(--surface)",
        border: "1.5px solid var(--line)",
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
      className={`cp-card${interactive ? " cp-card--interactive" : ""}`}
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--r-lg)",
        padding: "var(--sp-4)",
        boxShadow: "var(--shadow-1)",
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

/** 픽앤어스 브랜드 마크: 두 사람(보라·시안) 동그라미가 겹친 자리에 하트. */
export function BrandMark({ size = 28, decorative, style }: { size?: number; decorative?: boolean; style?: CSSProperties }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      style={{ display: "block", flex: "none", ...style }}
      aria-hidden={decorative ? true : undefined}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "픽앤어스"}
    >
      <circle cx="11.5" cy="16" r="9" fill="var(--owner)" opacity="0.9" />
      <circle cx="20.5" cy="16" r="9" fill="var(--partner)" opacity="0.85" />
      <path
        className="cp-beat"
        d="M16 21.2c-.3 0-.6-.1-.8-.3-2.7-2.3-4.1-3.7-4.1-5.4 0-1.4 1.1-2.5 2.4-2.5.9 0 1.8.5 2.5 1.3.7-.8 1.6-1.3 2.5-1.3 1.3 0 2.4 1.1 2.4 2.5 0 1.7-1.4 3.1-4.1 5.4-.2.2-.5.3-.8.3z"
        fill="var(--brand)"
        stroke="var(--surface)"
        strokeWidth="1.2"
      />
    </svg>
  );
}

export function Skeleton({ height = 16, width = "100%", style }: { height?: number | string; width?: number | string; style?: CSSProperties }) {
  return <div className="cp-skeleton" style={{ height, width, ...style }} aria-hidden />;
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div style={{ textAlign: "center", padding: "var(--sp-8) var(--sp-4)", color: "var(--text-muted)" }}>
      <BrandMark size={40} decorative style={{ margin: "0 auto var(--sp-3)" }} />
      <p className="cp-display" style={{ fontSize: "var(--fs-lg)", color: "var(--text)", marginBottom: "var(--sp-1)" }}>{title}</p>
      {description && <p style={{ fontSize: "var(--fs-sm)" }}>{description}</p>}
      {action}
    </div>
  );
}
