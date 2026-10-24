import { expect, test } from "@playwright/test";

test("archives, restores and permanently deletes an instrument", async ({ page }) => {
  let archived = false;
  let deleted = false;
  let purgeConfirmation = "";

  const instrument = () => ({
    id: 901,
    name: "测试银行",
    asset_type: "stock",
    path: "financial",
    industry: "银行",
    verdict: "观察",
    enabled: !archived,
    archived_at: archived ? "2026-10-25T00:00:00" : null,
    archive_reason: archived ? "手动移出标的库" : "",
    markets: ["A", "H"],
    listings: [
      { market: "A", code: "600036.SH", currency: "CNY", enabled: !archived },
      { market: "H", code: "03968.HK", currency: "HKD", enabled: !archived },
    ],
    report_count: 2,
    latest_analysis_date: "2026-10-24",
  });

  await page.route("**/api/v1/instruments", (route) =>
    route.fulfill({
      json: { items: deleted ? [] : [instrument()] },
    }),
  );
  await page.route("**/api/v1/instruments/901/restore", (route) => {
    archived = false;
    return route.fulfill({
      json: {
        instrument_id: 901,
        name: "测试银行",
        status: "active",
        archived_at: null,
        archive_reason: "",
      },
    });
  });
  await page.route("**/api/v1/instruments/901/purge?*", (route) => {
    purgeConfirmation = new URL(route.request().url()).searchParams.get("confirmation") ?? "";
    deleted = true;
    return route.fulfill({
      json: {
        instrument_id: 901,
        name: "测试银行",
        deleted_listings: 2,
        deleted_reports: 2,
        deleted_jobs: 1,
      },
    });
  });
  await page.route("**/api/v1/instruments/901", (route) => {
    archived = true;
    return route.fulfill({
      json: {
        instrument_id: 901,
        name: "测试银行",
        status: "archived",
        archived_at: "2026-10-25T00:00:00",
        archive_reason: "手动移出标的库",
      },
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "标的库" }).click();

  const row = page.locator(".instrument-library-row");
  await expect(row).toContainText("测试银行");
  await expect(row).toContainText("600036.SH");
  await expect(row).toContainText("03968.HK");

  await page.getByRole("button", { name: "删除 测试银行" }).click();
  await page.getByRole("button", { name: "移出榜单" }).click();
  await expect(row).toContainText("已归档");
  await expect(page.getByRole("button", { name: "恢复 测试银行" })).toBeVisible();

  await page.getByRole("button", { name: "恢复 测试银行" }).click();
  await expect(row).toContainText("当前");

  await page.getByRole("button", { name: "删除 测试银行" }).click();
  await page.getByRole("button", { name: "移出榜单" }).click();
  await page.getByRole("button", { name: "彻底删除 测试银行" }).click();

  const confirmation = page.getByPlaceholder("测试银行");
  await confirmation.fill("测试银行");
  await page.getByRole("button", { name: "永久删除" }).click();

  expect(purgeConfirmation).toBe("测试银行");
  await expect(page.getByText("标的库还是空的")).toBeVisible();
});
