import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: { jsx: "automatic" }, // React 17+ 자동 JSX 런타임
  test: {
    // E2E(Playwright)는 vitest 대상에서 제외
    exclude: ["e2e/**", "node_modules/**"],
    environment: "jsdom", // 컴포넌트 렌더 테스트용
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
