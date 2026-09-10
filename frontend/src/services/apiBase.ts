// API 주소 결정. 빌드 시점에 도메인을 박지 않는다.
//
// 이미지를 CI 에서 한 번 굽고 VM 은 pull 만 한다. 그런데 NEXT_PUBLIC_* 는 빌드
// 시점에 번들에 박히므로, 도메인을 빌드 인자로 받으면 도메인이 바뀔 때마다
// 이미지를 다시 구워야 한다. 그래서 브라우저에서는 현재 호스트로부터 API 주소를
// 유도하고(api.<도메인>), 서버(SSR)에서는 런타임 환경변수를 읽는다.

/** 브라우저에서 쓰는 API 주소. */
export function apiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE;
  if (configured) return configured; // 명시 설정이 있으면 그대로 따른다
  if (typeof window === "undefined") return serverApiBase();
  const { protocol, hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:8000"; // 로컬 개발
  }
  // 배포 규약: 프론트가 example.com 이면 API 는 api.example.com
  return `${protocol}//api.${hostname.replace(/^www\./, "")}`;
}

/** 서버(SSR)에서 쓰는 API 주소. 컨테이너 내부 주소를 런타임에 읽는다. */
export function serverApiBase(): string {
  return (
    process.env.API_INTERNAL_BASE ||
    process.env.NEXT_PUBLIC_API_BASE ||
    "http://localhost:8000"
  );
}
