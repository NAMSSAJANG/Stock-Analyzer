import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function shot(page: Page, name: string, project: string) {
  await page.screenshot({
    path: `../docs/screenshots/${project}-${name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
}
test("로그인 → 검색 → 종목 → 스크리너, 테마와 오프라인 보호", async ({
  page,
  context,
}, testInfo) => {
  await page.goto("/");
  await expect(page).toHaveURL(/login/);
  await shot(page, "login", testInfo.project.name);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByLabel("앱 비밀번호").fill("test-fixture-only");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "오늘의 리서치" }),
  ).toBeVisible();
  await shot(page, "home", testInfo.project.name);
  const cookie = (await context.cookies()).find(
    (c) => c.name === "goldnam_session",
  );
  expect(cookie).toMatchObject({
    secure: true,
    httpOnly: true,
    sameSite: "Lax",
  });
  await page.goto("/search/");
  await page
    .getByRole("textbox", { name: "종목 검색", exact: true })
    .fill("애플");
  await page.getByRole("button", { name: "검색", exact: true }).click();
  await expect(page.getByRole("link", { name: /AAPL Apple/ })).toBeVisible();
  await shot(page, "search", testInfo.project.name);
  await page.getByRole("link", { name: /AAPL Apple/ }).click();
  await expect(
    page.getByRole("heading", { name: "가격과 구조" }),
  ).toBeVisible();
  await expect(page.locator(".price-chart canvas").first()).toBeVisible();
  await shot(page, "stock", testInfo.project.name);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.goto("/screener/");
  await expect(page.locator(".filter-summary")).toContainText("2 종목");
  await shot(page, "screener", testInfo.project.name);
  if (testInfo.project.name !== "desktop") {
    await expect(page.locator(".desktop-table")).toBeHidden();
    await expect(page.locator(".bottom-nav a")).toHaveCount(5);
  }
  await page.goto("/settings/");
  await page.getByRole("button", { name: "Goldnam", exact: true }).click();
  await page.getByRole("button", { name: "설정 저장" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "goldnam");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
    "href",
    "/manifest-goldnam.webmanifest",
  );
  await shot(page, "settings-goldnam", testInfo.project.name);
  const manifest = await (
    await context.request.get("/manifest-goldnam.webmanifest")
  ).json();
  expect(manifest.display).toBe("standalone");
  for (const icon of manifest.icons)
    expect((await context.request.get(icon.src)).ok()).toBeTruthy();
  if (testInfo.project.name === "iphone") return; // WebKit test TLS cert cannot establish a trusted SW; Chromium covers offline.
  await page.evaluate(() => navigator.serviceWorker.ready);
  const cached = await page.evaluate(async () => {
    const keys = await caches.keys();
    return (
      await Promise.all(
        keys.map(async (k) =>
          (await (await caches.open(k)).keys()).map(
            (r) => new URL(r.url).pathname,
          ),
        ),
      )
    ).flat();
  });
  expect(cached.sort()).toEqual(["/offline.html", "/offline.js"]);
  await context.setOffline(true);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "연결 없음" })).toBeVisible();
  await expect(page.locator("#last-viewed")).not.toContainText("기록 없음");
  await shot(page, "offline", testInfo.project.name);
  await context.setOffline(false);
});
