import { io, type Socket } from "socket.io-client";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    // 자동 재연결 기본 활성 (5-4: 캐시 유실 시 서버 refetch + 재연결)
    socket = io(BASE, { transports: ["websocket"], autoConnect: true });
  }
  return socket;
}
