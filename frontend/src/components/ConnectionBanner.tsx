"use client";

import { useCourseStore } from "@/store/courseStore";

// 소켓 연결 끊김 안내 (5-4). 재연결 시 서버 상태 자동 refetch.
export default function ConnectionBanner() {
  const connected = useCourseStore((s) => s.connected);
  if (connected) return null;
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
