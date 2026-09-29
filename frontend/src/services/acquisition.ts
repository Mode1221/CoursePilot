// 첫 방문 출처(유입 경로) 기억하기.
//
// 처음 들어온 주소의 `src` 또는 `utm_source`(와 `utm_campaign`)를 기기에 남겨 두었다가
// 체험 시작·가입·카카오 로그인 때 서버로 보낸다. **처음 한 번만** 남긴다(first-touch) —
// 나중에 다른 링크로 다시 와도 덮어쓰지 않는다. 같이 정하기 링크(/together/<토큰>)로 온 사람은
// 그 토큰도 기억한다(가입하면 두 사람 모두 보상 — 초대자는 서버가 토큰으로 찾는다).
// 값 정리 규칙은 서버(app/referrals.py `clean_source`)와 같다: 소문자, [a-z0-9_-], 32자.

const KEY = "coursepilot_acq";
const MAX_LEN = 32;
// 초대 토큰은 이 기간이 지나면 보내지 않는다(오래전 링크로 뒤늦게 보상이 붙지 않게)
export const INVITE_TTL_MS = 30 * 24 * 60 * 60 * 1000;

export interface Acquisition {
  source?: string;
  campaign?: string;
  invite?: string;
  inviteAt?: number;
  at?: number;
}

/** 서버로 보내는 모양(빈 값은 뺀다). */
export interface ArrivalPayload {
  source?: string;
  campaign?: string;
  invite?: string;
}

export function sanitizeSource(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  const cleaned = value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, MAX_LEN);
  return cleaned || undefined;
}

const TOKEN_RE = /^\/together\/([A-Za-z0-9_-]{8,64})\/?$/;

/** 같이 정하기 링크 경로면 토큰. */
export function inviteTokenFromPath(pathname: string): string | undefined {
  return TOKEN_RE.exec(pathname)?.[1];
}

export function readAcquisition(): Acquisition {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as Acquisition) : {};
  } catch {
    return {};
  }
}

function write(acq: Acquisition): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(acq));
  } catch {
    /* 저장소가 막혀 있으면 기억하지 않는다(출처는 선택 정보) */
  }
}

/**
 * 처음 들어온 주소에서 출처를 뽑아 기억한다. 이미 첫 방문을 기억했으면 출처는 그대로 둔다.
 * 초대 토큰은 아직 없을 때만 남긴다(처음 받은 초대가 이긴다).
 */
export function captureAcquisition(search: string, pathname: string, now = Date.now()): Acquisition {
  const params = new URLSearchParams(search);
  const source = sanitizeSource(params.get("src")) ?? sanitizeSource(params.get("utm_source"));
  const campaign = sanitizeSource(params.get("utm_campaign"));
  const invite = inviteTokenFromPath(pathname);
  const prev = readAcquisition();
  const next: Acquisition = { ...prev };
  let changed = false;
  // 출처 없이 온 첫 방문도 "처음"으로 기록한다 — 그 뒤 광고 링크로 다시 와도 첫 출처는 직접 방문이다
  if (!prev.at) {
    next.source = source;
    next.campaign = campaign;
    next.at = now;
    changed = true;
  }
  if (invite && !prev.invite) {
    next.invite = invite;
    next.inviteAt = now;
    changed = true;
  }
  if (changed) write(next);
  return next;
}

/** 같이 정하기 화면이 직접 부른다(주소창과 무관하게 토큰을 확실히 남긴다). */
export function rememberInvite(token: string, now = Date.now()): void {
  captureAcquisition("", `/together/${token}`, now);
}

/** 체험 시작·가입 요청에 붙일 값. 출처를 적지 않았고 초대로 왔으면 서버가 "invite" 로 남긴다. */
export function arrivalPayload(now = Date.now()): ArrivalPayload {
  if (typeof window === "undefined") return {};
  const acq = readAcquisition();
  const out: ArrivalPayload = {};
  const source = sanitizeSource(acq.source);
  const campaign = sanitizeSource(acq.campaign);
  if (source) out.source = source;
  if (campaign) out.campaign = campaign;
  if (acq.invite && typeof acq.inviteAt === "number" && now - acq.inviteAt < INVITE_TTL_MS) {
    out.invite = acq.invite;
  }
  return out;
}

/** 회원이 되고 나면 지운다 — 서버가 첫 출처를 이미 갖고 있고, 초대 토큰은 한 번만 쓴다. */
export function clearAcquisition(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* 무시 */
  }
}
