"use client";

import { useCourseStore } from "@/store/courseStore";

// 소켓 연결 끊김 안내 (5-4). 재연결 시 서버 상태 자동 refetch.
export default function ConnectionBanner() {
  const connected = useCourseStore((s) => s.connected);
  const viewers = useCourseStore((s) => s.viewers);
  if (connected) {
    // 함께 보는 사람이 있을 때만 알린다(혼자면 방해가 된다)
    if (viewers < 2) return null;
    return (
      <div
        role="status"
        style={{
          background: "var(--surface-2)",
          color: "var(--text-muted)",
          borderBottom: "1px solid var(--border)",
          padding: "var(--sp-2) var(--sp-4)",
          fontSize: "var(--fs-sm)",
          textAlign: "center",
        }}
      >
        {viewers}명이 이 코스를 함께 보고 있어요.
      </div>
    );
  }
  return (
    <div
      role="status"
      style={{
        background: "var(--surface-2)",
        color: "var(--warn)",
        borderBottom: "1px solid var(--border)",
        padding: "var(--sp-2) var(--sp-4)",
        fontSize: "var(--fs-sm)",
        textAlign: "center",
      }}
    >
      실시간 연결이 끊겼습니다. 재연결되면 최신 상태로 동기화됩니다…
    </div>
  );
}
