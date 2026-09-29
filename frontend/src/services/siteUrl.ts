// 공유 미리보기(OG) 이미지 주소는 절대 URL 이어야 메신저가 가져간다.
//
// API 주소(apiBase.ts)와 같은 원칙: 빌드 시점에 도메인을 박지 않는다. 요청이 들어온 호스트
// (Caddy 가 넘기는 Host / X-Forwarded-*)에서 사이트 주소를 만든다. 런타임 환경변수 SITE_URL 이
// 있으면 그 값을 쓴다(프록시가 Host 를 바꾸는 배포용).

import { headers } from "next/headers";

interface HeaderLike {
  get(name: string): string | null;
}

// 호스트 헤더는 사용자가 보낼 수 있는 값이다 — 모양이 이상하면 쓰지 않는다
const HOST_RE = /^[a-z0-9.-]+(:\d{1,5})?$/i;

export function siteOrigin(headers: HeaderLike | null | undefined): URL | undefined {
  const configured = process.env.SITE_URL;
  if (configured) {
    try {
      return new URL(configured);
    } catch {
      /* 잘못된 설정은 무시하고 요청 호스트로 */
    }
  }
  if (!headers) return undefined;
  const host = (headers.get("x-forwarded-host") ?? headers.get("host") ?? "").split(",")[0].trim();
  if (!host || !HOST_RE.test(host)) return undefined;
  const local = /^(localhost|127\.0\.0\.1)(:|$)/.test(host);
  const forwarded = (headers.get("x-forwarded-proto") ?? "").split(",")[0].trim();
  const proto = forwarded === "http" || forwarded === "https" ? forwarded : local ? "http" : "https";
  try {
    return new URL(`${proto}://${host}`);
  } catch {
    return undefined;
  }
}

/**
 * 지금 요청의 사이트 주소(`metadataBase` 용). `headers()` 를 부르는 곳은 동적 렌더가 된다 —
 * 미리보기가 필요한 화면에서만 쓴다. Next 는 정적 생성 중단을 예외로 알리므로 여기서 잡지 않는다.
 */
export async function requestOrigin(): Promise<URL | undefined> {
  return siteOrigin(await headers());
}
