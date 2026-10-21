import { expect, test } from "@playwright/test";

test("switches risk profile and opens a valuation detail", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "把估值结论，压缩成可执行的排序。" }),
  ).toBeVisible();
  await expect(page.locator(".top-card")).toHaveCount(3);
  await expect(page.getByRole("table")).toBeVisible();

  await page.locator(".n-radio-button").filter({ hasText: "进取" }).click();
  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(
    page.locator(".n-radio-button").filter({ hasText: "进取" }).locator("input"),
  ).toBeChecked();

  const firstCard = page.locator(".top-card").first();
  await expect(firstCard).toContainText("宁德时代");
  await firstCard.click();

  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.locator(".n-drawer .detail-panel h1")).toContainText("宁德时代");
  await expect(page.getByText("价格相对合理区间")).toBeVisible();
  await expect(page.getByText("评分拆解")).toBeVisible();
  await expect(page.getByText("预期年化来自哪里")).toBeVisible();
});

test("keeps the ranking usable on a narrow screen", async ({ page }) => {
  await page.goto("/?profile=balanced");

  await expect(
    page.locator(".n-radio-button").filter({ hasText: "均衡" }).locator("input"),
  ).toBeChecked();
  await expect(page.locator(".freshness-bar")).toBeVisible();
  await expect(page.locator(".top-card").first()).toBeVisible();

  await page.locator(".top-card").first().click();
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.getByText("仓位与执行")).toBeVisible();
  await expect(page.getByText("关键风险与反证")).toBeVisible();
  await expect(page).toHaveURL(/profile=balanced/);
});
