"use client";

import { forwardRef } from "react";
import type { ButtonHTMLAttributes, CSSProperties, InputHTMLAttributes, ReactNode } from "react";

/** 공통 UI 프리미티브. 색·간격은 globals.css 토큰(var(--*))만 사용한다. */

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANT: Record<Variant, CSSProperties> = {
  primary: { background: "var(--brand)", color: "var(--brand-contrast)", border: "1px solid var(--brand)" },
  secondary: { background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)" },
  ghost: { background: "transparent", color: "var(--text-muted)", border: "1px solid transparent" },
  danger: { background: "transparent", color: "var(--danger)", border: "1px solid var(--border)" },
};

const SIZE: Record<Size, CSSProperties> = {
  sm: { padding: "6px 10px", fontSize: "var(--fs-sm)" },
  md: { padding: "10px 16px", fontSize: "var(--fs-md)" },
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; full?: boolean }
>(function Button({ variant = "secondary", size = "md", full, style, ...rest }, ref) {
  return (
    <button
      ref={ref}
      {...rest}
      style={{
        ...VARIANT[variant],
        ...SIZE[size],
        width: full ? "100%" : undefined,
        borderRadius: "var(--r-md)",
        fontWeight: 600,
        cursor: rest.disabled ? "not-allowed" : "pointer",
        opacity: rest.disabled ? 0.5 : 1,
        transition: "filter var(--dur) var(--ease), opacity var(--dur) var(--ease)",
        ...style,
      }}
    />
  );
});

export function Input({ style, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
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
}

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

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "brand" | "warn" }) {
  const tones = {
    neutral: { background: "var(--surface-2)", color: "var(--text-muted)" },
    brand: { background: "var(--brand-weak)", color: "var(--brand-strong)" },
    warn: { background: "var(--surface-2)", color: "var(--warn)" },
  } as const;
  return (
    <span
      style={{
        ...tones[tone],
        padding: "2px 8px",
        borderRadius: "var(--r-full)",
        fontSize: "var(--fs-xs)",
        fontWeight: 600,
        whiteSpace: "nowrap",
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
