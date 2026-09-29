import { defineConfig, devices } from "@playwright/test";

// 운영 사이트 자동 점검(GitHub Actions `qa.yml`). 로컬 서버를 띄우지 않고 실제 배포본을 친다.
//   QA_BASE_URL  사이트 주소(기본 https://coursepilot-kr.duckdns.org)
//   QA_API_URL   API 주소(기본 https://api.<사이트 호스트>)
//   QA_TOKEN     있으면 로그인 흐름까지(전용 QA 회원, 학습 신호 미기록). 없으면 헬스·페이지만.
const base = process.env.QA_BASE_URL || "https://coursepilot-kr.duckdns.org";

export default defineConfig({
  testDir: "./e2e-prod",
  timeout: 90_000,
  fullyParallel: false,
  retries: 1, // 네트워크 한 번 흔들린 걸로 경보를 울리지 않는다
  reporter: [["list"], ["json", { outputFile: "qa-report.json" }]],
  use: {
    baseURL: base,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // 모든 요청(브라우저 → API 포함)에 QA 표시 — 서버가 학습 신호를 쌓지 않는다
    extraHTTPHeaders: process.env.QA_TOKEN ? { "X-QA-Token": process.env.QA_TOKEN } : {},
  },
  projects: [
    {
      name: "mobile",
      use: {
        ...devices["Pixel 7"],
        // 사전 설치된 크로미움 경로가 있으면 사용(로컬), 없으면 기본(CI 설치본)
        launchOptions: process.env.PW_CHROME_PATH ? { executablePath: process.env.PW_CHROME_PATH } : {},
      },
    },
  ],
});
