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
  await page.getByRole("button", { name: "코스 만들고 링크 보내기" }).click();
  await page.getByLabel("조건 입력").fill(text);
  await page.getByText("전송").click();
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible({ timeout: 15_000 });
  // 처리 중에는 입력이 잠긴다 — 다음 요청을 보내려면 풀릴 때까지 기다려야 한다
  await expect(page.getByLabel("조건 입력")).toBeEnabled({ timeout: 15_000 });
}

test("참여자(비로그인)는 AI 챗봇을 쓸 수 없다", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "코스 만들고 링크 보내기" }).click();
  await expect(page.getByText(/참여자는 수동 편집만 가능/)).toBeVisible();
});

test("생성자는 코스를 생성하고 타임라인을 본다", async ({ page }) => {
  await asMember(page);
  await createCourse(page, "성수동 오전 10시 5시간 코스 도보");

  // AI 응답 + 타임라인 렌더 확인 (특정 장소명 대신 순번 프리픽스로 일반화)
  await expect(page.getByText(/곳으로 코스를 구성했어요/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/1\. 성수동 장소/)).toBeVisible();
  // 검증 기간 무료(FREE_MODE 기본 true): 잔여 횟수·포인트 구매는 보이지 않고, AI 사용 고지가 보인다
  await expect(page.getByText(/질문 \d+회 남음/)).toHaveCount(0);
  await expect(page.getByText("포인트 구매")).toHaveCount(0);
  await expect(page.getByRole("note")).toContainText("AI가 만든 추천");
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
  // 저장 요청이 끝나기 전에 페이지를 떠나면 가끔 저장이 누락된다(flaky) → 응답을 기다린다
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/preferences") && r.request().method() !== "GET" && r.ok()),
    page.getByText("저장").click(),
  ]);

  await page.goto("/onboarding");
  await expect(page.getByPlaceholder("예: 성수동")).toHaveValue("연남동", { timeout: 10_000 });
});

test("먼저 상대에게 묻기: 링크 → 상대 카드 → 합친 코스에 반영 칩 → 둘 다 수락", async ({ page, context }) => {
  await asMember(page);
  await page.goto("/");
  await page.getByRole("button", { name: "코스 만들고 링크 보내기" }).click();
  await page.getByLabel("내 이름").fill("민수");
  await page.getByLabel("상대 이름").fill("지은");
  await page.getByLabel("언제 어디서").fill("토요일 3시 성수");
  await page.getByText("링크 만들기").click();

  // 내 카드
  await page.getByText("고기").click();
  await page.getByText("웨이팅").click();
  await page.getByText("내 카드 저장").click();
  await expect(page.getByText("민수 카드 ✓")).toBeVisible();

  // 상대는 다른 브라우저 컨텍스트(비가입)에서 링크를 연다
  const link = (await page.locator("code").first().textContent())?.trim();
  expect(link).toContain("/together/");
  const partner = await context.browser()!.newPage();
  await partner.goto(link!);
  await expect(partner.getByText(/같이 정하재요 · 30초 · 가입 없음/)).toBeVisible();
  await partner.getByText("피곤해 (많이 못 걸어)").click();
  await partner.getByText("디저트").click();
  await partner.getByText("매운 거").click();
  await partner.getByText("보냈어요").click();
  await expect(partner.getByText(/보냈어요 ✨/)).toBeVisible();

  // 합치기 → 이름으로 된 반영 칩(코스 전체 조건은 요약 줄)
  await expect(page.getByText(/지은 답함/)).toBeVisible({ timeout: 10_000 });
  await page.getByText("둘의 카드 합쳐서 코스 만들기").click();
  await expect(page.getByRole("list", { name: "코스 전체에 반영된 의견" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/지은 매운 거/).first()).toBeVisible();
  // 양쪽 반영: 상대의 취향(디저트)도 칸이나 요약 어딘가에 이름으로 드러난다
  await expect(page.getByText(/지은 디저트/).first()).toBeVisible();
  await expect(page.getByText(/민수 고기/).first()).toBeVisible();

  // 수락: 시작한 사람 → 상대는 링크에서 "코스 보러 가기"로 편집 가능한 코스 화면에 들어간다
  await page.getByText("이 코스 좋아요").click();
  await expect(partner.getByText("코스 보러 가기")).toBeVisible({ timeout: 15_000 });
  await partner.getByText("코스 보러 가기").click();
  await expect(partner.getByText(/민수님과 같이 정하는 중/)).toBeVisible({ timeout: 10_000 });
  // 상대도 편집 버튼과 챗봇을 쓴다(가입 없이, 링크 토큰으로)
  await expect(partner.getByRole("button", { name: "교체" }).first()).toBeVisible();
  await expect(partner.getByText(/같이 정하는 중 · AI에게 바로 말해 보세요/)).toBeVisible();
  // 실시간: 상대가 한 칸을 지우면 시작한 사람 화면에 새로고침 없이 반영된다
  await expect(page.getByText(/^1\. /)).toBeVisible();
  const before = await page.getByText(/^\d+\. /).count();
  await partner.getByRole("button", { name: "삭제" }).first().click();
  await expect(page.getByText(/^\d+\. /)).toHaveCount(before - 1, { timeout: 10_000 });
  await partner.getByText("이 코스 좋아요").click();
  await expect(partner.getByText(/둘 다 좋아요 · 확정/)).toBeVisible({ timeout: 10_000 });

  // 카드 수정: 상대가 답을 고치면 시작한 사람에게 "다시 합치기" 안내, 수락은 초기화
  await partner.getByText("내 카드 수정").click();
  await expect(partner.getByText("수정한 답 보내기")).toBeVisible();
  await expect(partner.getByText("← 코스로 돌아가기")).toBeVisible(); // 모바일 웹뷰에서도 돌아갈 길
  await expect(partner.getByText("디저트")).toHaveAttribute("aria-pressed", "true"); // 이전 답이 채워져 있다
  await partner.getByText("양식").click();
  await partner.getByText("수정한 답 보내기").click();
  await expect(page.getByText(/카드가 바뀌었어요/)).toBeVisible({ timeout: 10_000 });
  await partner.close();

  // 새 코스로 옮기면 이전 코스의 타임라인이 남지 않는다
  const oldUrl = page.url();
  await page.getByRole("button", { name: "+ 새 코스" }).click();
  await expect(page).not.toHaveURL(oldUrl);
  await expect(page.getByText("아직 코스가 없어요")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/^1\. /)).toHaveCount(0);

  // 코스 화면에서 빠져나가기: 내 코스
  await page.getByRole("link", { name: "내 코스" }).click();
  await expect(page).toHaveURL(/\/mypage/);
});
