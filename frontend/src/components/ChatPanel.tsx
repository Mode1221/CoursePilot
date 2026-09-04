"use client";

import { useState } from "react";

import { api } from "@/services/api";
import { shareService } from "@/services/shareService";
import { useCourseStore } from "@/store/courseStore";

export default function ChatPanel({ courseId }: { courseId: string }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const locked = useCourseStore((s) => s.locked);
  const setCourse = useCourseStore((s) => s.setCourse);
  const course = useCourseStore((s) => s.course);

  async function send() {
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      const updated = await api.generate(courseId, text);
      setCourse(updated);
      setText("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: 12, borderBottom: "1px solid #eee", display: "flex", justifyContent: "space-between" }}>
        <strong>{course?.title ?? "코스"}</strong>
        <button onClick={() => shareService.share(window.location.href)}>공유</button>
      </div>

      <div style={{ flex: 1, padding: 12, overflow: "auto", color: "#666" }}>
        예: &quot;토요일 오후 1시 성수동, 3시간짜리 코스, 도보 10분 이내&quot;
        {locked && <p style={{ color: "#c60" }}>AI 처리 중… 편집이 잠깁니다.</p>}
      </div>

      <div style={{ padding: 12, borderTop: "1px solid #eee", display: "flex", gap: 8 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="조건을 입력하세요"
          disabled={sending}
          style={{ flex: 1, padding: 8 }}
        />
        <button onClick={send} disabled={sending || locked}>
          {sending ? "..." : "전송"}
        </button>
      </div>
    </div>
  );
}
