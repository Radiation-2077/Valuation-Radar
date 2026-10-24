import { expect, test } from "@playwright/test";

test("adds an instrument and queues a valuation job", async ({ page }) => {
  let submitted: Record<string, unknown> | null = null;
  await page.route("**/api/v1/instruments", async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        instrument_id: 7,
        job_id: 42,
        name: "测试银行",
        market: "A",
        code: "600036.SH",
        currency: "CNY",
        asset_type: "stock",
        status: "queued",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "添加标的" }).click();
  await page.getByPlaceholder("例如：招商银行").fill("测试银行");
  await page
    .getByPlaceholder("不记得可留空：600036.SH、sh600036、00700.HK")
    .fill("600036.SH");
  await page.getByRole("button", { name: "添加并开始估值" }).click();

  expect(submitted).toEqual({
    name: "测试银行",
    code: "600036.SH",
    asset_type: "stock",
  });
  await expect(page.getByText("Codex 任务 #42 已排队", { exact: false })).toBeVisible();
});

test("allows submitting only a name so Codex can discover the listing market", async ({
  page,
}) => {
  let submitted: Record<string, unknown> | null = null;
  await page.route("**/api/v1/instruments", async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        instrument_id: 8,
        job_id: 43,
        name: "仅名称标的",
        market: null,
        code: null,
        currency: null,
        asset_type: "stock",
        status: "queued",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "添加标的" }).click();
  await page.getByPlaceholder("例如：招商银行").fill("仅名称标的");
  await page.getByRole("button", { name: "添加并开始估值" }).click();

  expect(submitted).toEqual({
    name: "仅名称标的",
    asset_type: "stock",
  });
  await expect(page.getByText("Codex 任务 #43 已排队", { exact: false })).toBeVisible();
});
