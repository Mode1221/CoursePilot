/** @type {import('next').NextConfig} */
const nextConfig = {
  // 런타임 스테이지에 node_modules 전체를 넣지 않기 위해 standalone 출력을 쓴다.
  output: "standalone",
  // next/image 를 쓰지 않는다. 이미지 최적화 엔드포인트(/_next/image)는 Next 14 에서 원격 코드 실행
  // 취약점(GHSA, 15.5.24 에서 수정)이 있어 아예 끈다.
  images: { unoptimized: true },
  env: {
    // 비워 두면 브라우저가 현재 호스트에서 api.<도메인> 을 유도한다
    // (services/apiBase.ts). 그래야 도메인마다 이미지를 다시 굽지 않는다.
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "",
    NEXT_PUBLIC_NAVER_MAP_CLIENT_ID: process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID || "",
  },
};

export default nextConfig;
