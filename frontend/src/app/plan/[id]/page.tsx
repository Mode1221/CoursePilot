"use client";

import { useEffect } from "react";

import ChatPanel from "@/components/ChatPanel";
import MapPanel from "@/components/MapPanel";
import { api } from "@/services/api";
import { getSocket } from "@/services/socket";
import { useCourseStore } from "@/store/courseStore";
import type { Course } from "@/types";

export default function PlanPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const setCourse = useCourseStore((s) => s.setCourse);
  const setLocked = useCourseStore((s) => s.setLocked);

  useEffect(() => {
    api.getCourse(id).then(setCourse).catch(() => {});

    const socket = getSocket();
    socket.emit("join", { course_id: id });
    socket.on("state", (course: Course) => setCourse(course));
    socket.on("locked", () => setLocked(true));
    socket.on("unlocked", () => setLocked(false));

    return () => {
      socket.off("state");
      socket.off("locked");
      socket.off("unlocked");
    };
  }, [id, setCourse, setLocked]);

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <div style={{ flex: 1, borderRight: "1px solid #eee", overflow: "auto" }}>
        <MapPanel />
      </div>
      <div style={{ width: 380, display: "flex", flexDirection: "column" }}>
        <ChatPanel courseId={id} />
      </div>
    </div>
  );
}
