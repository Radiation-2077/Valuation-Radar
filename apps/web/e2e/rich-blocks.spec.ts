import { expect, test } from "@playwright/test";

test("renders structured formulas, rich text, bullets and tables", async ({ page }) => {
  const rankingResponse = await page.request.get("/api/v1/rankings?profile=balanced");
  expect(rankingResponse.ok()).toBe(true);
  const ranking = await rankingResponse.json();
  const valuationMarketId = ranking.main_board[0].valuation_market_id as number;

  await page.route(`**/api/v1/valuations/${valuationMarketId}*`, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.report_detail.sections = [
      {
        id: "cross_market_formula",
        title: "A/H 溢价公式预览",
        market: "common",
        blocks: [
          {
            type: "formula",
            latex:
              "\\frac{D}{P_A}(1-t_A)+g=\\frac{D}{P_H}(1-t_H)+g \\Longrightarrow \\frac{P_A}{P_H}=\\frac{1-t_A}{1-t_H}",
            caption: "同一现金流下，A/H 税后股息率应相等",
          },
          {
            type: "table",
            headers: ["投资者类型", "合理比价", "A 合理溢价"],
            rows: [
              ["个人长期（A 0% vs H 20%）", "1.25", "+25%"],
              ["个人（A 0% vs H 10%）", "1.11", "+11%"],
              ["企业免税（0% vs 0%）", "1.00", "0%"],
            ],
          },
          {
            type: "bullets",
            items: [
              "**股息率越高**，税费差对合理溢价的影响越大",
              "低股息、高成长标的受影响较小",
            ],
          },
          {
            type: "callout",
            tone: "info",
            title: "政策提示",
            body: "红利税政策以税务机关最新口径为准，变动会直接改变合理溢价。",
            summary: true,
          },
        ],
      },
    ];
    await route.fulfill({ response, json: payload });
  });

  await page.goto(`/valuations/${valuationMarketId}?profile=balanced`);
  await expect(page.getByRole("heading", { name: "A/H 溢价公式预览" })).toBeVisible();
  await expect(page.locator(".math-formula--display .katex").first()).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "个人长期（A 0% vs H 20%）" }),
  ).toBeVisible();
  await expect(page.getByText("低股息、高成长标的受影响较小")).toBeVisible();
  await expect(page.getByText("政策提示")).toBeVisible();
});
