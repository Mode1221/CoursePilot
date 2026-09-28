import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const API = "http://localhost:8000";

// 자동 검사로 잡을 수 있는 접근성 위반(대비·이름 없는 버튼·라벨·랜드마크 등)을 페이지마다 0 으로 유지한다.
// serious·critical 만 막는다 — minor 는 보고만(디자인 판단이 필요한 경우가 있다).
async function expectNoSeriousViolations(page: import("@playwright/test").Page, name: string) {
  await page.waitForTimeout(600); // 등장 애니메이션 중에는 배경이 반투명이라 대비가 틀리게 잡힌다
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const summary = serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
  expect(summary, `${name} 접근성 위반`).toEqual([]);
}

async function member(page: import("@playwright/test").Page) {
  const res = await fetch(`${API}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: `010-${Date.now()}` }),
  });
  const body = await res.json();
  await page.addInitScript(
    ([uid, tok]) => {
      localStorage.setItem("coursepilot_user_id", uid);
      if (tok) localStorage.setItem("coursepilot_user_token", tok);
    },
    [body.user_id, body.token ?? ""],
  );
}

for (const scheme of ["light", "dark"] as const) {
  for (const path of ["/", "/onboarding", "/terms", "/privacy", "/mypage"]) {
    test(`접근성(${scheme}): ${path}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await member(page);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoSeriousViolations(page, `${scheme} ${path}`);
    });
  }
}

for (const [label, viewport, scheme] of [
  ["넓은 화면", { width: 1280, height: 800 }, "light"],
  ["휴대폰 다크", { width: 390, height: 844 }, "dark"],
] as const) test(`접근성: 코스 화면과 AI 채팅 — ${label}`, async ({ page }) => {
  await page.setViewportSize(viewport);
  await page.emulateMedia({ colorScheme: scheme });
  await member(page);
  await page.goto("/");
  await page.getByRole("button", { name: "코스 만들고 링크 보내기" }).click();
  await page.getByRole("button", { name: "AI로 코스 고치기" }).click({ timeout: 15_000 });
  await page.getByLabel("조건 입력").fill("성수동 오전 10시 5시간 도보");
  await page.getByText("전송").click();
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible({ timeout: 15_000 });
  await expectNoSeriousViolations(page, "코스 화면");
  await page.getByRole("button", { name: "AI로 코스 고치기" }).click();
  await expectNoSeriousViolations(page, "AI 채팅 열림");
});

test("키보드만으로 AI 채팅을 열고 보내고 닫는다", async ({ page }) => {
  await member(page);
  await page.goto("/");
  await page.getByRole("button", { name: "코스 만들고 링크 보내기" }).click();
  const fab = page.getByRole("button", { name: "AI로 코스 고치기" });
  await fab.waitFor({ timeout: 15_000 });
  await fab.focus();
  await page.keyboard.press("Enter");
  const input = page.getByLabel("조건 입력");
  await expect(input).toBeVisible();
  await input.focus();
  await page.keyboard.type("성수동 오전 10시 5시간 도보");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible({ timeout: 15_000 });
  await fab.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "AI 챗봇" })).toBeVisible();
  await expect(page.getByLabel("조건 입력")).toBeFocused(); // 열면 바로 입력할 수 있다
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "AI 챗봇" })).toHaveCount(0);
  await expect(fab).toBeFocused(); // 닫으면 여는 버튼으로 돌아온다
});
