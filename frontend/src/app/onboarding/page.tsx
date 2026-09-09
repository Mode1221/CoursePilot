"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Input } from "@/components/ui";
import { ApiError, api } from "@/services/api";
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

// 예산 문항 값은 백엔드 BUDGET_CHOICES 와 1:1 로 맞춘다(문자열이 그대로 저장된다).
const BUDGET_OPTIONS = ["2만원 이하", "2~4만원", "4~6만원", "6만원 이상"];
// 검색 키워드로 그대로 전달되는 제약(식이·동반 조건)
const DIET_OPTIONS = ["비건", "채식", "노키즈", "반려동물"];

// 온보딩 선호 사전조사 (9-6). 5문항, 모두 건너뛰기 가능.
export default function Onboarding() {
  const router = useRouter();
  const { userId, load, setUser } = useUserStore();
  const [phone, setPhone] = useState("");
  const [mood, setMood] = useState("");
  const [region, setRegion] = useState("");
  const [transport, setTransport] = useState("");
  const [budget, setBudget] = useState("");
  const [diet, setDiet] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    load();
  }, [load]);

  async function sendCode() {
    if (sending) return;
    setError(null);
    if (!PHONE_RE.test(phone.trim())) {
      setError("휴대폰 번호를 010-0000-0000 형식으로 입력해 주세요.");
      return;
    }
    setSending(true);
    try {
      const res = await api.requestSmsCode(phone.trim());
      setCodeSent(true);
      // 개발 환경(SMS 키 미설정)에서는 코드가 응답으로 오므로 바로 채워 준다
      if (res.dev_code) setCode(res.dev_code);
      toast("인증번호를 보냈어요.", "success");
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 429
          ? "잠시 후 다시 요청해 주세요."
          : "인증번호를 보내지 못했어요. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setSending(false);
    }
  }

  async function verifyCode() {
    if (sending) return;
    setError(null);
    setSending(true);
    try {
      await api.verifySmsCode(phone.trim(), code.trim());
      setVerified(true);
      toast("인증됐어요.", "success");
    } catch {
      setError("인증번호가 올바르지 않거나 만료됐어요. 다시 받아 주세요.");
    } finally {
      setSending(false);
    }
  }

  function toggleDiet(value: string) {
    setDiet((prev) => (prev.includes(value) ? prev.filter((d) => d !== value) : [...prev, value]));
  }

  async function submit() {
    if (saving) return; // 중복 제출 방지
    setError(null);
    let id = userId;
    if (!id) {
      if (!PHONE_RE.test(phone.trim())) {
        setError("휴대폰 번호를 010-0000-0000 형식으로 입력해 주세요.");
        return;
      }
      if (!verified) {
        setError("휴대폰 인증을 먼저 완료해 주세요.");
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
        budget: budget || null,
        diet,
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
          <>
            <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
              전화번호
              <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-1)" }}>
                <Input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="010-0000-0000"
                  inputMode="tel"
                  disabled={verified}
                  style={{ flex: 1 }}
                />
                <Button onClick={sendCode} disabled={sending || verified}>
                  {codeSent ? "다시 받기" : "인증번호 받기"}
                </Button>
              </div>
            </label>

            {codeSent && !verified && (
              <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
                인증번호
                <div style={{ display: "flex", gap: "var(--sp-2)", marginTop: "var(--sp-1)" }}>
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="6자리"
                    inputMode="numeric"
                    maxLength={6}
                    aria-label="인증번호"
                    style={{ flex: 1 }}
                  />
                  <Button onClick={verifyCode} disabled={sending || code.trim().length !== 6}>
                    확인
                  </Button>
                </div>
              </label>
            )}

            {verified && (
              <p style={{ color: "var(--brand-strong)", fontSize: "var(--fs-sm)", margin: 0 }}>
                휴대폰 인증 완료
              </p>
            )}
          </>
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

        <label style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
          1인 예산대
          <select value={budget} onChange={(e) => setBudget(e.target.value)} style={FIELD}>
            <option value="">선택 안 함</option>
            {BUDGET_OPTIONS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>

        <fieldset
          style={{ border: "none", padding: 0, margin: 0, fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}
        >
          <legend style={{ padding: 0 }}>빼고 싶은 것 (복수 선택)</legend>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)", marginTop: "var(--sp-2)" }}>
            {DIET_OPTIONS.map((d) => (
              <label
                key={d}
                style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text)" }}
              >
                <input
                  type="checkbox"
                  checked={diet.includes(d)}
                  onChange={() => toggleDiet(d)}
                />
                {d}
              </label>
            ))}
          </div>
        </fieldset>
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
