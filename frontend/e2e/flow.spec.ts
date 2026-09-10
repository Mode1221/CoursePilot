import { expect, test } from "@playwright/test";

const API = "http://localhost:8000";

// 로그인 회원 세션을 만들고 localStorage 에 주입
async function signup(): Promise<{ userId: string; token: string }> {
  const res = await fetch(`${API}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: `010-${Date.now()}` }),
  });
  const body = await res.json();
  return { userId: body.user_id, token: body.token ?? "" };
}

/** 로그인 세션(회원 id + 서명 토큰)을 브라우저에 주입한다. */
async function asMember(page: import("@playwright/test").Page) {
  const { userId, token } = await signup();
  await page.addInitScript(
    ([uid, tok]) => {
      localStorage.setItem("coursepilot_user_id", uid);
      if (tok) localStorage.setItem("coursepilot_user_token", tok);
    },
    [userId, token],
  );
  return userId;
}

/** 코스를 하나 만들고 타임라인이 뜰 때까지 기다린다. */
async function createCourse(page: import("@playwright/test").Page, text: string) {
  await page.goto("/");
  await page.getByText("새 코스 시작").click();
  await page.getByLabel("조건 입력").fill(text);
  await page.getByText("전송").click();
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible({ timeout: 15_000 });
  // 처리 중에는 입력이 잠긴다 — 다음 요청을 보내려면 풀릴 때까지 기다려야 한다
  await expect(page.getByLabel("조건 입력")).toBeEnabled({ timeout: 15_000 });
}

test("참여자(비로그인)는 AI 챗봇을 쓸 수 없다", async ({ page }) => {
  await page.goto("/");
  await page.getByText("새 코스 시작").click();
  await expect(page.getByText(/참여자는 수동 편집만 가능/)).toBeVisible();
});

test("생성자는 코스를 생성하고 타임라인을 본다", async ({ page }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 코스 도보");

  // AI 응답 + 타임라인 렌더 확인 (특정 장소명 대신 순번 프리픽스로 일반화)
  await expect(page.getByText(/곳으로 코스를 구성했어요/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible();
  await expect(page.getByText(/질문 \d+회 남음/)).toBeVisible();
});

test("장소 상세 모달이 리뷰 요약을 보여준다", async ({ page }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 도보");
  await page.getByText(/1\. 성수동 장소/).click();

  await expect(page.getByRole("heading", { name: "리뷰 요약" })).toBeVisible();
});

test("삭제한 장소를 되돌리기로 복원한다", async ({ page }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 도보");

  const first = await page.getByText(/1\. 성수동 장소/).innerText();
  await page.getByRole("button", { name: "삭제" }).first().click();
  await expect(page.getByText(first, { exact: true })).toHaveCount(0);

  await page.getByLabel("되돌리기").click();
  await expect(page.getByText(first, { exact: true })).toBeVisible();
});



test("질문에는 코스를 바꾸지 않고 답한다", async ({ page }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 도보");
  const before = await page.getByText(/1\. 성수동 장소/).innerText();

  await page.getByLabel("조건 입력").fill("주차 되나요?");
  await page.getByText("전송").click();

  // 주차를 물었으면 주차로 답하고, 코스는 그대로다
  await expect(page.getByText(/주차/).last()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(before, { exact: true })).toBeVisible();
});

test("자리를 집어 다른 성격으로 바꾼다", async ({ page }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 도보");
  const first = await page.getByText(/1\. 성수동 장소/).innerText();

  await page.getByLabel("조건 입력").fill("첫번째를 카페로 바꿔줘");
  await page.getByText("전송").click();

  await expect(page.getByText(/바꿨어요/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(first, { exact: true })).toHaveCount(0);
});

test("공유 링크는 편집 없이 코스를 보여준다", async ({ page, context }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 도보");
  const url = page.url();

  // 세션 없는 새 탭에서 열어도 코스는 보이고, 편집 버튼은 없다
  const guest = await context.newPage();
  await guest.addInitScript(() => localStorage.clear());
  await guest.goto(url);
  await expect(guest.getByText(/1\. 성수동 장소/)).toBeVisible({ timeout: 15_000 });
  await expect(guest.getByText(/참여자는 수동 편집만 가능/)).toBeVisible();
});

test("온보딩에서 선호를 저장하면 다시 열었을 때 채워져 있다", async ({ page }) => {
  await asMember(page);
  await page.goto("/onboarding");
  await page.getByPlaceholder("예: 성수동").fill("연남동");
  await page.getByLabel("분위기").selectOption("조용한");
  await page.getByText("저장").click();

  await page.goto("/onboarding");
  await expect(page.getByPlaceholder("예: 성수동")).toHaveValue("연남동", { timeout: 10_000 });
});
