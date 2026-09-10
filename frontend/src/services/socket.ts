import { io, type Socket } from "socket.io-client";

import { apiBase } from "@/services/apiBase";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    // 자동 재연결 기본 활성 (5-4: 캐시 유실 시 서버 refetch + 재연결)
    socket = io(apiBase(), { transports: ["websocket"], autoConnect: true });
  }
  return socket;
}
