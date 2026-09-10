/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    // 비워 두면 브라우저가 현재 호스트에서 api.<도메인> 을 유도한다
    // (services/apiBase.ts). 그래야 도메인마다 이미지를 다시 굽지 않는다.
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "",
    NEXT_PUBLIC_NAVER_MAP_CLIENT_ID: process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID || "",
  },
};

export default nextConfig;
