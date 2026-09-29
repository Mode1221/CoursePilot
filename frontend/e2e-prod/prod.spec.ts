import { expect, test, type Page } from "@playwright/test";

// 운영 사이트 점검 — 사람이 매번 눌러 보던 핵심 흐름을 몇 시간마다 대신 확인한다.
const BASE = process.env.QA_BASE_URL || "https://coursepilot-kr.duckdns.org";
const API = process.env.QA_API_URL || `https://api.${new URL(BASE).host}`;
const QA_TOKEN = process.env.QA_TOKEN || "";

test("API 가 살아 있고 DB 가 붙어 있다", async ({ request }) => {
  const res = await request.get(`${API}/health`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body.status).toBe("ok");
  const env = process.env.QA_EXPECT_ENV || "production";
  expect(body.env).toBe(env);
  if (env === "production") expect(body.db).toBe(true); // 운영은 DB 없이 뜨면 안 된다(인메모리면 재시작 때 다 사라진다)
});

for (const [path, text] of [
  ["/", "데이트 계획"],
  ["/start", "가입 없이 한 번 써 보기"],
  ["/login", "로그인"],
  ["/terms", "이용약관"],
  ["/privacy", "개인정보처리방침"],
] as const) {
  test(`페이지가 열린다: ${path}`, async ({ page }) => {
    const res = await page.goto(path);
    expect(res?.status(), `${path} 응답 코드`).toBeLessThan(400);
    await expect(page.getByRole("heading").first()).toContainText(text);
  });
}

test("로그인 화면에 로그인 수단이 하나 이상 있다", async ({ page }) => {
  await page.goto("/login");
  const kakao = page.getByRole("button", { name: "카카오로 계속하기" });
  const phone = page.getByText("전화번호로 로그인");
  await expect(kakao.or(phone).first()).toBeVisible({ timeout: 15_000 });
});

async function asQaMember(page: Page) {
  const res = await page.request.post(`${API}/admin/qa-session`, { headers: { "X-QA-Token": QA_TOKEN } });
  expect(res.ok(), "QA 세션 발급").toBeTruthy();
  const s = await res.json();
  await page.addInitScript(
    ([uid, tok]) => {
      localStorage.setItem("coursepilot_user_id", uid);
      localStorage.setItem("coursepilot_user_token", tok);
      localStorage.setItem("coursepilot_user_kind", "member");
    },
    [s.user_id, s.token],
  );
  return { userId: s.user_id as string, token: s.token as string };
}

test("같이 정하기: 링크 → 상대 카드 → 자동 합치기 → 수락 → 공유 화면", async ({ page, browser }) => {
  test.skip(!QA_TOKEN, "QA_TOKEN 이 없어 로그인 흐름은 건너뜀");
  const me = await asQaMember(page);

  await page.goto("/");
  await page.getByRole("button", { name: "코스 만들고 링크 보내기" }).click();
  await expect(page).toHaveURL(/\/plan\//, { timeout: 20_000 });
  const courseId = page.url().split("/plan/")[1].split(/[?#]/)[0];

  try {
    await page.getByLabel("내 이름").fill("QA민수");
    await page.getByLabel("상대 이름").fill("QA지은");
    await page.getByLabel("언제 어디서").fill("토요일 3시 성수");
    await page.getByText("링크 만들기").click();
    await page.getByText("고기").click();
    await page.getByText("웨이팅").click(); // "빼줘"는 하나 골라야 저장된다
    await page.getByText("내 카드 저장").click();
    await expect(page.getByText("QA민수 카드 ✓")).toBeVisible({ timeout: 15_000 });

    const link = (await page.locator("code").first().textContent())?.trim();
    expect(link).toContain("/together/");

    // 상대: 가입 없이 다른 브라우저에서
    const ctx = await browser.newContext({
      extraHTTPHeaders: QA_TOKEN ? { "X-QA-Token": QA_TOKEN } : {},
    });
    const partner = await ctx.newPage();
    await partner.goto(link!);
    await partner.getByText("피곤해 (많이 못 걸어)").click();
    await partner.getByText("디저트").click();
    await partner.getByText("매운 거").click();
    await partner.getByText("보냈어요").click();

    // 두 카드가 모이면 자동으로 합친다
    await expect(partner.getByText(/합친 코스가 준비됐어요/)).toBeVisible({ timeout: 45_000 });
    await expect(page.getByRole("list", { name: "코스 전체에 반영된 의견" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/^1\. /).first()).toBeVisible();

    // 수락
    await page.getByText("이 코스 좋아요").click();
    await partner.getByText("코스 보러 가기").click();
    await partner.getByText("이 코스 좋아요").click();
    await expect(partner.getByText(/둘 다 좋아요 · 확정/)).toBeVisible({ timeout: 20_000 });
    await ctx.close();

    // 공유 링크: 신원 없이 열면 읽기 전용
    const viewer = await browser.newContext();
    const v = await viewer.newPage();
    await v.goto(`/plan/${courseId}`);
    await expect(v.getByText(/^1\. /).first()).toBeVisible({ timeout: 20_000 });
    await expect(v.getByRole("button", { name: "교체" })).toHaveCount(0);
    await viewer.close();
  } finally {
    // 점검 코스는 남기지 않는다
    await page.request.delete(`${API}/courses/${courseId}`, {
      headers: { "X-User-Id": me.userId, "X-User-Token": me.token, "X-QA-Token": QA_TOKEN },
    });
  }
});
