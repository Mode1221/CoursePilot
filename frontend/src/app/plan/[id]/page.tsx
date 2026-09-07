"use client";

import { useEffect, useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import ConnectionBanner from "@/components/ConnectionBanner";
import MapPanel from "@/components/MapPanel";
import { useIsNarrow } from "@/hooks/useIsNarrow";
import { api } from "@/services/api";
import { getSocket } from "@/services/socket";
import { useCourseStore } from "@/store/courseStore";
import type { Course } from "@/types";

export default function PlanPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const setCourse = useCourseStore((s) => s.setCourse);
  const setLocked = useCourseStore((s) => s.setLocked);
  const setStage = useCourseStore((s) => s.setStage);
  const setMessages = useCourseStore((s) => s.setMessages);
  const appendMessage = useCourseStore((s) => s.appendMessage);
  const setConnected = useCourseStore((s) => s.setConnected);
  const setNotFound = useCourseStore((s) => s.setNotFound);
  const notFound = useCourseStore((s) => s.notFound);
  const narrow = useIsNarrow();
  const [tab, setTab] = useState<"map" | "chat">("map");

  useEffect(() => {
    // 캐시 유실/재연결 시 서버에서 현재 상태 refetch (5-4)
    const refetch = () => {
      api.getCourse(id).then(setCourse).catch(() => setNotFound(true));
      api.messages(id).then(setMessages).catch(() => {});
    };
    refetch();

    const socket = getSocket();
    setConnected(socket.connected);
    socket.emit("join", { course_id: id });
    socket.on("state", (course: Course) => setCourse(course));
    socket.on("locked", () => setLocked(true));
    socket.on("unlocked", () => {
      setLocked(false);
      setStage(null);
    });
    socket.on("progress", (d: { stage: string }) => setStage(d.stage));
    socket.on("message", (m: { role: "user" | "ai"; text: string }) => appendMessage(m));
    socket.on("connect", () => {
      setConnected(true);
      socket.emit("join", { course_id: id });
      refetch(); // 재연결 시 로컬 캐시 복원 대신 서버 상태로 동기화
    });
    socket.on("disconnect", () => setConnected(false));

    return () => {
      socket.off("state");
      socket.off("locked");
      socket.off("unlocked");
      socket.off("progress");
      socket.off("message");
      socket.off("connect");
      socket.off("disconnect");
    };
  }, [id, setCourse, setLocked, setStage, setMessages, appendMessage, setConnected, setNotFound]);

  if (notFound) {
    return (
      <main style={{ padding: 48, maxWidth: 640, margin: "0 auto" }}>
        <h1>코스를 찾을 수 없습니다</h1>
        <p style={{ color: "#888" }}>링크가 잘못되었거나 삭제된 코스일 수 있어요.</p>
        <a href="/">새 코스 시작하기</a>
      </main>
    );
  }

  // 좁은 화면(웹뷰/모바일): 지도·챗봇을 탭 전환식 세로 레이아웃으로
  if (narrow) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <ConnectionBanner />
        <div role="tablist" aria-label="화면 전환" style={{ display: "flex", borderBottom: "1px solid #eee" }}>
          {(["map", "chat"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              style={{
                flex: 1,
                padding: 12,
                border: "none",
                background: tab === t ? "#fff" : "#f2f4f7",
                fontWeight: tab === t ? 600 : 400,
                borderBottom: tab === t ? "2px solid #0f9d84" : "2px solid transparent",
              }}
            >
              {t === "map" ? "지도·타임라인" : "AI 챗봇"}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, overflow: "auto", display: tab === "map" ? "block" : "none" }}>
          <MapPanel />
        </div>
        <div style={{ flex: 1, overflow: "hidden", display: tab === "chat" ? "flex" : "none", flexDirection: "column" }}>
          <ChatPanel courseId={id} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <ConnectionBanner />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ flex: 1, borderRight: "1px solid #eee", overflow: "auto" }}>
          <MapPanel />
        </div>
        <div style={{ width: 380, display: "flex", flexDirection: "column" }}>
          <ChatPanel courseId={id} />
        </div>
      </div>
    </div>
  );
}
