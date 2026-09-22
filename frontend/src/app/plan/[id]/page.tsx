"use client";

import { useEffect, useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import ConnectionBanner from "@/components/ConnectionBanner";
import MapPanel from "@/components/MapPanel";
import AppNav from "@/components/AppNav";
import NotFound from "@/components/NotFound";
import PartnerBar from "@/components/PartnerBar";
import TogetherPanel from "@/components/TogetherPanel";
import { useIsNarrow } from "@/hooks/useIsNarrow";
import { api } from "@/services/api";
import { getSocket } from "@/services/socket";
import { useCourseStore } from "@/store/courseStore";
import type { Course } from "@/types";

export default function PlanPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const setCourse = useCourseStore((s) => s.setCourse);
  const clearCourse = useCourseStore((s) => s.clearCourse);
  const setLocked = useCourseStore((s) => s.setLocked);
  const setStage = useCourseStore((s) => s.setStage);
  const setMessages = useCourseStore((s) => s.setMessages);
  const appendMessage = useCourseStore((s) => s.appendMessage);
  const setConnected = useCourseStore((s) => s.setConnected);
  const setViewers = useCourseStore((s) => s.setViewers);
  const setNotFound = useCourseStore((s) => s.setNotFound);
  const notFound = useCourseStore((s) => s.notFound);
  const narrow = useIsNarrow();
  const [tab, setTab] = useState<"map" | "chat">("map");
  const [chatOpen, setChatOpen] = useState(true);

  useEffect(() => {
    setNotFound(false); // 다른 코스로 이동 시 이전 404 상태 초기화
    clearCourse(); // 새 코스로 옮기면 이전 코스(지도·타임라인)가 남아 보이던 문제
    setMessages([]);
    // 캐시 유실/재연결 시 서버에서 현재 상태 refetch (5-4)
    // 다른 코스로 이동하면 이전 코스의 늦은 응답이 현재 화면을 덮어쓸 수 있다
    let cancelled = false;
    const refetch = () => {
      api
        .getCourse(id)
        .then((course) => {
          if (!cancelled) setCourse(course);
        })
        .catch(() => {
          if (!cancelled) setNotFound(true);
        });
      api
        .messages(id)
        .then((messages) => {
          if (!cancelled) setMessages(messages);
        })
        .catch(() => {});
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
    socket.on("presence", (d: { count: number }) => setViewers(d.count));
    socket.on("message", (m: { role: "user" | "ai"; text: string }) => appendMessage(m));
    socket.on("connect", () => {
      setConnected(true);
      socket.emit("join", { course_id: id });
      refetch(); // 재연결 시 로컬 캐시 복원 대신 서버 상태로 동기화
    });
    socket.on("disconnect", () => setConnected(false));

    return () => {
      cancelled = true;
      socket.emit("leave", { course_id: id }); // 떠난 코스의 브로드캐스트를 계속 받지 않는다
      socket.off("state");
      socket.off("locked");
      socket.off("unlocked");
      socket.off("progress");
      socket.off("presence");
      socket.off("message");
      socket.off("connect");
      socket.off("disconnect");
    };
  }, [
    id,
    setCourse,
    clearCourse,
    setLocked,
    setStage,
    setMessages,
    appendMessage,
    setConnected,
    setNotFound,
    setViewers,
  ]);

  if (notFound) {
    return <NotFound message="링크가 잘못되었거나 삭제된 코스일 수 있어요." />;
  }

  // 좁은 화면(웹뷰/모바일): 지도·챗봇을 탭 전환식 세로 레이아웃으로
  if (narrow) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
        <AppNav />
        <ConnectionBanner />
        <div
          role="tablist"
          aria-label="화면 전환"
          onKeyDown={(e) => {
            // 좌우 화살표로 탭을 옮기는 건 탭 위젯의 기본 조작이다
            if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
            e.preventDefault();
            const next = tab === "map" ? "chat" : "map";
            setTab(next);
            document.getElementById(`tab-${next}`)?.focus();
          }}
          style={{ display: "flex", borderBottom: "1px solid var(--border)" }}
        >
          {(["map", "chat"] as const).map((t) => (
            <button
              key={t}
              id={`tab-${t}`}
              role="tab"
              aria-selected={tab === t}
              aria-controls={`panel-${t}`}
              // 선택되지 않은 탭은 Tab 키 순회에서 빼는 게 탭 위젯 규칙(로빙 tabindex)
              tabIndex={tab === t ? 0 : -1}
              onClick={() => setTab(t)}
              style={{
                flex: 1,
                padding: 12,
                border: "none",
                background: tab === t ? "var(--surface)" : "var(--bg-subtle)",
                color: tab === t ? "var(--text)" : "var(--text-muted)",
                fontWeight: tab === t ? 600 : 400,
                borderBottom: tab === t ? "2px solid var(--brand)" : "2px solid transparent",
                cursor: "pointer",
              }}
            >
              {t === "map" ? "지도·타임라인" : "AI 챗봇"}
            </button>
          ))}
        </div>
        <div
          id="panel-map"
          role="tabpanel"
          aria-labelledby="tab-map"
          style={{ flex: 1, overflow: "auto", display: tab === "map" ? "block" : "none" }}
        >
          <div style={{ padding: "var(--sp-4) var(--sp-4) 0" }}>
            <TogetherPanel courseId={id} />
            <PartnerBar courseId={id} />
          </div>
          <MapPanel />
        </div>
        <div
          id="panel-chat"
          role="tabpanel"
          aria-labelledby="tab-chat"
          style={{ flex: 1, overflow: "hidden", display: tab === "chat" ? "flex" : "none", flexDirection: "column" }}
        >
          <ChatPanel courseId={id} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <AppNav />
      <ConnectionBanner />
      {/* 넓은 화면: 위 — 같이 정하기 / 가운데 — 큰 지도 + 오른쪽 타임라인 / 아래 — 채팅(접기 가능) */}
      <div style={{ padding: "var(--sp-3) var(--sp-4) 0" }}>
        <TogetherPanel courseId={id} />
        <PartnerBar courseId={id} />
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <MapPanel split />
      </div>
      <section
        aria-label="AI 챗봇"
        style={{
          height: chatOpen ? 232 : 40,
          borderTop: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          transition: "height var(--dur) var(--ease)",
          position: "relative",
        }}
      >
        <button
          type="button"
          onClick={() => setChatOpen((o) => !o)}
          aria-expanded={chatOpen}
          style={{
            // 채팅 위 경계선에 걸친 손잡이 — 채팅 헤더의 버튼(다녀왔어요·캘린더·공유)을 가리지 않는다
            position: "absolute",
            left: "50%",
            transform: "translate(-50%, -50%)",
            top: 0,
            zIndex: 2,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            borderRadius: "var(--r-full)",
            padding: "2px 10px",
            fontSize: "var(--fs-xs)",
            cursor: "pointer",
          }}
        >
          {chatOpen ? "채팅 접기 ▾" : "채팅 열기 ▴"}
        </button>
        {chatOpen && (
          <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <ChatPanel courseId={id} />
          </div>
        )}
        {!chatOpen && (
          <div style={{ padding: "10px 16px", fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
            AI 챗봇 — {"\u201c2번 다른 곳으로\u201d, \u201c매운 거 빼줘\u201d"}
          </div>
        )}
      </section>
    </div>
  );
}
