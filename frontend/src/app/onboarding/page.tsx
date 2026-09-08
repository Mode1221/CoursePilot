"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Input } from "@/components/ui";
import { api } from "@/services/api";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

const FIELD: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "10px 12px",
  fontSize: "var(--fs-md)",
  color: "var(--text)",
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-md)",
  marginTop: "var(--sp-1)",
};

// 휴대폰 번호(하이픈 유무 모두 허용)
const PHONE_RE = /^01[016789]-?\d{3,4}-?\d{4}$/;

// 온보딩 선호 사전조사 (9-6). 모든 문항 건너뛰기 가능.
export default function Onboarding() {
  const router = useRouter();
  const { userId, load, setUser } = useUserStore();
  const [phone, setPhone] = useState("");
  const [mood, setMood] = useState("");
  const [region, setRegion] = useState("");
  const [transport, setTransport] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
  }, [load]);

  async function submit() {
    if (saving) return; // 중복 제출 방지
    setError(null);
    let id = userId;
    if (!id) {
      if (!PHONE_RE.test(phone.trim())) {
        setError("휴대폰 번호를 010-0000-0000 형식으로 입력해 주세요.");
        return;
      }
    }
    setSaving(true);
    try {
      if (!id) {
        const res = await api.signup(phone.trim());
        setUser(res.user_id);
        id = res.user_id;
      }
      await api.setPreferences(id, {
        mood: mood || null,
        region: region || null,
        transport: transport || null,
        diet: [],
      });
      toast("설정을 저장했어요.", "success");
      router.push("/");
    } catch {
      setError("저장에 실패했어요. 잠시 후 다시 시도해 주세요.");
      setSaving(false);
    }
  }

  return (
    <main style={{ padding: "var(--sp-12) var(--sp-4)", maxWidth: 460, margin: "0 auto" }}>
      <h1>선호 설정</h1>
      <p style={{ color: "var(--text-muted)" }}>
        모두 선택 사항이에요. 짧게 입력하면 AI가 나머지를 자동으로 보완합니다.
      </p>

      <div style={{ display: "grid", gap: "var(--sp-4)", marginTop: "var(--sp-6)" }}>
        {!userId && (
          <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
            전화번호
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="010-0000-0000"
              inputMode="tel"
              style={{ display: "block", width: "100%", marginTop: "var(--sp-1)" }}
            />
          </label>
        )}

        <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          분위기
          <select value={mood} onChange={(e) => setMood(e.target.value)} style={FIELD}>
            <option value="">선택 안 함</option>
            <option value="조용한">조용한</option>
            <option value="활기찬">활기찬</option>
          </select>
        </label>

        <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          자주 가는 지역
          <Input
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="예: 성수동"
            style={{ display: "block", width: "100%", marginTop: "var(--sp-1)" }}
          />
        </label>

        <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          이동수단
          <select value={transport} onChange={(e) => setTransport(e.target.value)} style={FIELD}>
            <option value="">선택 안 함</option>
            <option value="도보">도보</option>
            <option value="차량">차량</option>
          </select>
        </label>
      </div>

      {error && (
        <p
          role="alert"
          style={{ color: "var(--danger)", fontSize: "var(--fs-sm)", marginTop: "var(--sp-3)" }}
        >
          {error}
        </p>
      )}

      <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-6)" }}>
        <Button variant="primary" onClick={submit} disabled={saving}>
          {saving ? "저장 중…" : "저장"}
        </Button>
        <Button variant="ghost" onClick={() => router.push("/")} disabled={saving}>
          건너뛰기
        </Button>
      </div>
    </main>
  );
}
