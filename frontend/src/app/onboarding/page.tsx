"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/services/api";
import { useUserStore } from "@/store/userStore";

// 온보딩 선호 사전조사 (9-6). 모든 문항 건너뛰기 가능.
export default function Onboarding() {
  const router = useRouter();
  const { userId, load, setUser } = useUserStore();
  const [phone, setPhone] = useState("");
  const [mood, setMood] = useState("");
  const [region, setRegion] = useState("");
  const [transport, setTransport] = useState("");

  useEffect(() => {
    load();
  }, [load]);

  async function submit() {
    let id = userId;
    if (!id) {
      if (!phone.trim()) return alert("전화번호 인증이 필요합니다");
      const res = await api.signup(phone);
      setUser(res.user_id);
      id = res.user_id;
    }
    await api.setPreferences(id, {
      mood: mood || null,
      region: region || null,
      transport: transport || null,
      diet: [],
    });
    router.push("/");
  }

  return (
    <main style={{ padding: 48, maxWidth: 480, margin: "0 auto" }}>
      <h1>선호 설정</h1>
      <p style={{ color: "#888" }}>모두 선택 사항입니다. 짧게 입력하면 AI가 나머지를 자동 보완합니다.</p>

      {!userId && (
        <label style={{ display: "block", margin: "12px 0" }}>
          전화번호
          <input value={phone} onChange={(e) => setPhone(e.target.value)} style={{ display: "block", width: "100%", padding: 8 }} />
        </label>
      )}

      <label style={{ display: "block", margin: "12px 0" }}>
        분위기
        <select value={mood} onChange={(e) => setMood(e.target.value)} style={{ display: "block", width: "100%", padding: 8 }}>
          <option value="">선택 안 함</option>
          <option value="조용한">조용한</option>
          <option value="활기찬">활기찬</option>
        </select>
      </label>

      <label style={{ display: "block", margin: "12px 0" }}>
        자주 가는 지역
        <input value={region} onChange={(e) => setRegion(e.target.value)} style={{ display: "block", width: "100%", padding: 8 }} />
      </label>

      <label style={{ display: "block", margin: "12px 0" }}>
        이동수단
        <select value={transport} onChange={(e) => setTransport(e.target.value)} style={{ display: "block", width: "100%", padding: 8 }}>
          <option value="">선택 안 함</option>
          <option value="도보">도보</option>
          <option value="차량">차량</option>
        </select>
      </label>

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button onClick={submit}>저장</button>
        <button onClick={() => router.push("/")} style={{ background: "none" }}>
          건너뛰기
        </button>
      </div>
    </main>
  );
}
