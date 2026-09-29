import { io, type Socket } from "socket.io-client";

import { apiBase } from "@/services/apiBase";
import { readTogetherToken } from "@/services/togetherToken";
import { storedUserId, storedUserToken } from "@/store/userStore";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    // 자동 재연결 기본 활성 (5-4: 캐시 유실 시 서버 refetch + 재연결)
    socket = io(apiBase(), { transports: ["websocket"], autoConnect: true });
  }
  return socket;
}

/**
 * 코스 방 입장 요청. 신원(서명 토큰)이나 상대 링크 토큰을 함께 보내야 대화 메시지도 받는다 —
 * 공유 링크로 보는 사람은 코스 상태만 받는다.
 */
export function joinPayload(courseId: string): Record<string, string> {
  const payload: Record<string, string> = { course_id: courseId };
  const uid = storedUserId();
  const token = storedUserToken();
  const partner = readTogetherToken(courseId);
  if (uid) payload.user_id = uid;
  if (token) payload.user_token = token;
  if (partner) payload.together_token = partner;
  return payload;
}
