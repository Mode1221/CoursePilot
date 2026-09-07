import { expect, test } from "@playwright/test";

const API = "http://localhost:8000";

// 로그인 회원 세션을 만들고 localStorage 에 주입
async function signup(): Promise<string> {
  const res = await fetch(`${API}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: `010-${Date.now()}` }),
  });
  return (await res.json()).user_id;
}

test("참여자(비로그인)는 AI 챗봇을 쓸 수 없다", async ({ page }) => {
  await page.goto("/");
  await page.getByText("새 코스 시작").click();
  await expect(page.getByText("참여자는 수동 편집만 가능합니다.")).toBeVisible();
});

test("생성자는 코스를 생성하고 타임라인을 본다", async ({ page }) => {
  const userId = await signup();
  await page.addInitScript((uid) => localStorage.setItem("coursepilot_user_id", uid), userId);

  await page.goto("/");
  await page.getByText("새 코스 시작").click();
  await page.getByPlaceholder("조건을 입력하세요").fill("성수동 오전 10시 5시간 코스 도보");
  await page.getByText("전송").click();

  // AI 응답 + 타임라인 렌더 확인 (특정 장소명 대신 순번 프리픽스로 일반화)
  await expect(page.getByText(/곳으로 코스를 구성했어요/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible();
  await expect(page.getByText(/질문 \d+회 남음/)).toBeVisible();
});

test("장소 상세 모달이 리뷰 요약을 보여준다", async ({ page }) => {
  const userId = await signup();
  await page.addInitScript((uid) => localStorage.setItem("coursepilot_user_id", uid), userId);

  await page.goto("/");
  await page.getByText("새 코스 시작").click();
  await page.getByPlaceholder("조건을 입력하세요").fill("성수동 오전 10시 5시간 도보");
  await page.getByText("전송").click();
  await page.getByText(/1\. 성수동 장소/).click();

  await expect(page.getByRole("heading", { name: "리뷰 요약" })).toBeVisible();
});
