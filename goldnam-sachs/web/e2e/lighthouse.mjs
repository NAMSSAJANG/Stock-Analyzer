import { chromium } from "@playwright/test";
import lighthouse from "lighthouse";
import { writeFile, mkdir } from "node:fs/promises";
const browser = await chromium.launch({
  args: ["--remote-debugging-port=9223", "--ignore-certificate-errors"],
});
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  await page.goto("https://localhost:8765/login/");
  await page.getByLabel("앱 비밀번호").fill("test-fixture-only");
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await page.waitForURL("https://localhost:8765/");
  await mkdir("../docs/lighthouse", { recursive: true });
  // Pass a fixture-only cookie in memory; never put session values into report files.
  const cookies = await context.cookies();
  const cookie = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  const summaries = [];
  for (const [name, url] of [
    ["login", "/login/"],
    ["stock", "/stock/?symbol=AAPL"],
  ]) {
    const result = await lighthouse(`https://localhost:8765${url}`, {
      port: 9223,
      output: ["html", "json"],
      logLevel: "error",
      onlyCategories: ["performance", "accessibility", "best-practices"],
      disableStorageReset: true,
      extraHeaders: { Cookie: cookie },
    });
    const lhr = result.lhr;
    delete lhr.configSettings.extraHeaders;
    await writeFile(
      `../docs/lighthouse/${name}.json`,
      JSON.stringify(lhr, null, 2),
    );
    summaries.push({
      page: name,
      scores: Object.fromEntries(
        Object.entries(lhr.categories).map(([k, v]) => [k, v.score]),
      ),
      failed: Object.entries(lhr.audits)
        .filter(([, v]) => v.score === 0)
        .map(([k]) => k),
    });
  }
  await writeFile(
    "../docs/lighthouse/summary.json",
    JSON.stringify(summaries, null, 2),
  );
  console.log(JSON.stringify(summaries, null, 2));
} finally {
  await browser.close();
}
