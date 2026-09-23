"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import type { TogetherCard, TogetherStatus } from "@/services/api";

const CONDITION_LABEL: Record<TogetherCard["condition"], string> = {
  fresh: "쌩쌩",
  normal: "보통",
  tired: "피곤해 (많이 못 걸어)",
  hungry: "배고플 듯 (바로 밥)",
};
const BUDGET_LABEL: Record<number, string> = { 20000: "~2만원", 30000: "~3만원", 50000: "~5만원", 0: "상관없어" };

/**
 * 30초 카드 4장. 탭만으로 답하고, "아무거나"를 고르면 싫은 것 카드를 강조한다 —
 * 좋아하는 걸 말하긴 어려워도 싫은 걸 말하긴 쉽다.
 * 서로의 답은 합치기 전까지 보이지 않는다(눈치·앵커링 방지).
 */
interface Saved {
  condition: TogetherCard["condition"];
  cravings: string[];
  dislikes: string[];
  budget: number | null;
  note: string;
}

function readSaved(key?: string): Saved | null {
  if (!key) return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Saved) : null;
  } catch {
    return null;
  }
}

export default function TogetherCards({
  spec,
  submitLabel = "보냈어요",
  onSubmit,
  storageKey,
}: {
  spec: TogetherStatus["cards"];
  submitLabel?: string;
  onSubmit: (card: TogetherCard) => Promise<void>;
  /** 고른 그대로(아무거나·없음 포함)를 이 기기에 남겨, 수정할 때 다시 채운다. 서버엔 저장하지 않는다. */
  storageKey?: string;
}) {
  const [saved] = useState(() => (typeof window === "undefined" ? null : readSaved(storageKey)));
  const [condition, setCondition] = useState<TogetherCard["condition"]>(saved?.condition ?? "normal");
  const [cravings, setCravings] = useState<string[]>(saved?.cravings ?? []);
  const [dislikes, setDislikes] = useState<string[]>(saved?.dislikes ?? []);
  const [budget, setBudget] = useState<number | null>(saved?.budget ?? null);
  const [note, setNote] = useState(saved?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const anything = cravings.includes("아무거나");

  function toggle(list: string[], set: (v: string[]) => void, v: string, exclusive?: string) {
    if (list.includes(v)) return set(list.filter((x) => x !== v));
    if (exclusive && v === exclusive) return set([v]);
    set([...list.filter((x) => x !== exclusive), v]);
  }

  async function submit() {
    if (cravings.length === 0) return setError("땡기는 걸 하나만 골라주세요. 정말 없으면 '아무거나'도 좋아요.");
    if (dislikes.length === 0) return setError("이건 빼줘, 하나만 골라주세요. 없으면 '없음'.");
    setError(null);
    setBusy(true);
    try {
      await onSubmit({
        condition,
        cravings: cravings.filter((c) => c !== "아무거나"),
        dislikes: dislikes.filter((d) => d !== "없음"),
        budget_band: budget,
        note: note.trim() || undefined,
      });
      if (storageKey) {
        try {
          window.localStorage.setItem(storageKey, JSON.stringify({ condition, cravings, dislikes, budget, note }));
        } catch {
          /* storage 막힘 */
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: "var(--sp-6)" }}>
      <Section title="그날 컨디션은?">
        <Chips
          options={spec.conditions}
          label={(c) => CONDITION_LABEL[c as TogetherCard["condition"]] ?? c}
          selected={[condition]}
          onPick={(c) => setCondition(c as TogetherCard["condition"])}
        />
      </Section>
      <Section title="요즘 땡기는 건?">
        <Chips
          options={spec.cravings}
          selected={cravings}
          onPick={(c) => toggle(cravings, setCravings, c, "아무거나")}
        />
        {anything && (
          <p style={{ margin: "var(--sp-2) 0 0", color: "var(--partner)", fontSize: "var(--fs-sm)", fontWeight: 500 }}>
            좋아요, 그럼 이것만 피할게요 ↓
          </p>
        )}
      </Section>
      <Section title="이건 빼줘" highlight={anything}>
        <Chips options={spec.dislikes} selected={dislikes} onPick={(d) => toggle(dislikes, setDislikes, d, "없음")} />
      </Section>
      <Section title="1인 예산은?">
        <p style={{ margin: "0 0 var(--sp-2)", fontSize: "var(--fs-sm)", color: "var(--text-faint)" }}>선택 · 상대에겐 안 보여요</p>
        <Chips
          options={spec.budget_bands.map(String)}
          label={(b) => BUDGET_LABEL[Number(b)] ?? b}
          selected={budget === null ? [] : [String(budget)]}
          onPick={(b) => setBudget(budget === Number(b) ? null : Number(b))}
        />
      </Section>
      <Section title="하고 싶은 거 있으면 한마디">
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={200}
          placeholder="예: 팝업 가보고 싶어…"
          aria-label="한마디"
          autoComplete="off"
          enterKeyHint="done"
          style={{
            width: "100%",
            padding: "12px 14px",
            border: "1.5px solid var(--line)",
            borderRadius: "var(--r-md)",
            font: "inherit",
            background: "var(--surface)",
          }}
        />
      </Section>
      {error && (
        <p role="alert" style={{ margin: 0, color: "var(--danger)", fontSize: "var(--fs-sm)" }}>
          {error}
        </p>
      )}
      <Button variant="primary" full onClick={submit} disabled={busy}>
        {busy ? "보내는 중…" : submitLabel}
      </Button>
    </div>
  );
}

function Section({ title, children, highlight }: { title: string; children: React.ReactNode; highlight?: boolean }) {
  // 각 카드는 하나의 질문 = fieldset. 강조(아무거나 → 싫은 것)는 배경이 아니라 왼쪽 선으로.
  return (
    <fieldset
      style={{
        border: 0,
        margin: 0,
        padding: "0 0 0 var(--sp-4)",
        borderLeft: `3px solid ${highlight ? "var(--partner)" : "var(--line)"}`,
        transition: "border-color var(--dur) var(--ease)",
      }}
    >
      <legend style={{ padding: 0, marginBottom: "var(--sp-3)", fontWeight: 700, fontSize: "var(--fs-lg)", letterSpacing: "-.01em" }}>
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

function Chips({
  options,
  selected,
  onPick,
  label,
}: {
  options: string[];
  selected: string[];
  onPick: (v: string) => void;
  label?: (v: string) => string;
}) {
  return (
    <div role="group" style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)" }}>
      {options.map((o) => {
        const on = selected.includes(o);
        return (
          <button
            key={o}
            type="button"
            aria-pressed={on}
            onClick={() => onPick(o)}
            style={{
              padding: "11px 16px",
              minHeight: 44,
              borderRadius: "var(--r-full)",
              border: `1.5px solid ${on ? "var(--brand)" : "var(--line)"}`,
              background: on ? "var(--brand-weak)" : "var(--surface)",
              color: on ? "var(--brand-strong)" : "var(--text)",
              font: "inherit",
              fontSize: "var(--fs-md)",
              fontWeight: on ? 600 : 500,
              cursor: "pointer",
            }}
          >
            {label ? label(o) : o}
          </button>
        );
      })}
    </div>
  );
}
