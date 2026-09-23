"use client";

import { useEffect, useState } from "react";

import AiChatFab from "@/components/AiChatFab";
import CourseActionBar from "@/components/CourseActionBar";
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

const FAB_GUTTER = 76; // 떠 있는 버튼 높이 + 위아래 여백

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

  // 좁은 화면: 한 줄로 스크롤(같이 정하기 → 지도 → 타임라인), 아래 고정 줄(다녀왔어요·캘린더·공유),
  // AI 채팅은 떠 있는 버튼 → 아래에서 올라오는 시트.
  // 넓은 화면: 위 — 같이 정하기 / 가운데 — 큰 지도 + 오른쪽 타임라인 / 아래 — 고정 줄, 채팅은 떠 있는 패널.
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <AppNav />
      <ConnectionBanner />
      {narrow ? (
        <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
          <div style={{ padding: "var(--sp-3) var(--sp-4) 0" }}>
            <TogetherPanel courseId={id} />
            <PartnerBar courseId={id} />
          </div>
          <MapPanel />
          <div style={{ height: 72 }} aria-hidden="true" />
        </div>
      ) : (
        <>
          <div style={{ padding: "var(--sp-3) var(--sp-4) 0" }}>
            <TogetherPanel courseId={id} />
            <PartnerBar courseId={id} />
          </div>
          {/* 아래 여백(FAB_GUTTER)은 떠 있는 "AI에게 말하기" 버튼 자리 — 카드가 버튼 위에서 끝나고
              아래 고정 줄과도 떨어져 보이게 */}
          <div style={{ flex: 1, minHeight: 0, paddingBottom: FAB_GUTTER }}>
            <MapPanel split />
          </div>
        </>
      )}
      <CourseActionBar courseId={id} />
      <AiChatFab courseId={id} narrow={narrow} />
    </div>
  );
}
