"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/services/api";
import { shareService } from "@/services/shareService";
import { useCourseStore } from "@/store/courseStore";
import { useUserStore } from "@/store/userStore";

const STAGE_LABELS: Record<string, string> = {
  decomposition: "조건 분석",
  search: "후보 수집",
  validation: "영업시간·이동 검증",
  relaxing: "조건 완화 재시도",
  editing: "부분 수정 반영",
  done: "마무리",
};

function stageLabel(stage: string | null): string {
  return stage ? STAGE_LABELS[stage] ?? stage : "";
}

export default function ChatPanel({ courseId }: { courseId: string }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const locked = useCourseStore((s) => s.locked);
  const stage = useCourseStore((s) => s.stage);
  const messages = useCourseStore((s) => s.messages);
  const setCourse = useCourseStore((s) => s.setCourse);
  const course = useCourseStore((s) => s.course);

  const { userId, questionsLeft, load, setQuestionsLeft } = useUserStore();

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (userId) api.credits(userId).then((c) => setQuestionsLeft(c.questions_left)).catch(() => {});
  }, [userId, setQuestionsLeft]);

  async function send() {
    if (!text.trim() || sending) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const res = await api.generate(courseId, text, userId ?? undefined);
      setCourse(res.course);
      setText("");
      if (res.needs_confirmation) {
        setNotice("조건에 맞는 장소가 부족합니다. 조건을 완화할까요?");
      } else if (res.relaxed) {
        setNotice("일부 조건을 완화해 코스를 구성했습니다.");
      }
      if (userId) api.credits(userId).then((c) => setQuestionsLeft(c.questions_left)).catch(() => {});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "요청 실패");
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: 12, borderBottom: "1px solid #eee", display: "flex", justifyContent: "space-between" }}>
        <strong>{course?.title ?? "코스"}</strong>
        <button onClick={() => shareService.share(`${window.location.origin}/share/${courseId}`)}>
          공유
        </button>
      </div>

      <div style={{ flex: 1, padding: 12, overflow: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {messages.length === 0 && (
          <p style={{ color: "#999", fontSize: 13 }}>
            예: &quot;토요일 오후 1시 성수동, 3시간짜리 코스, 도보 10분 이내&quot;
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
              padding: "8px 11px",
              borderRadius: 12,
              fontSize: 14,
              background: m.role === "user" ? "#0f9d84" : "#f2f4f7",
              color: m.role === "user" ? "#fff" : "#222",
            }}
          >
            {m.text}
          </div>
        ))}
        {userId != null && questionsLeft != null && (
          <p style={{ color: "#888", fontSize: 12 }}>질문 {questionsLeft}회 남음</p>
        )}
        {userId == null && (
          <p style={{ color: "#888", fontSize: 12 }}>참여자는 수동 편집만 가능합니다.</p>
        )}
        {locked && <p style={{ color: "#c60" }}>AI 처리 중… {stageLabel(stage)} · 편집이 잠깁니다.</p>}
        {notice && <p style={{ color: "#c60" }}>{notice}</p>}
        {error && <p style={{ color: "#c00" }}>{error}</p>}
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
