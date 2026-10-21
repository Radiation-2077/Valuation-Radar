import { expect, test } from "@playwright/test";

test("switches risk profile and opens a valuation detail", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "把估值结论，压缩成可执行的排序。" }),
  ).toBeVisible();
  await expect(page.locator(".top-card")).toHaveCount(3);
  await expect(page.getByRole("table")).toBeVisible();

  await page.getByRole("tab", { name: /进取/ }).click();
  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(page.getByRole("tab", { name: /进取/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  const firstCard = page.locator(".top-card").first();
  await expect(firstCard).toContainText("宁德时代");
  await firstCard.click();

  await expect(page).toHaveURL(/\/valuations\/\d+\?profile=aggressive/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("宁德时代");
  await expect(page.getByText("价格相对合理区间")).toBeVisible();
  await expect(page.getByText("评分拆解")).toBeVisible();
  await expect(page.getByText("预期年化来自哪里")).toBeVisible();
});

test("keeps the ranking usable on a narrow screen", async ({ page }) => {
  await page.goto("/?profile=balanced");

  await expect(page.getByRole("tab", { name: /均衡/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.locator(".freshness-bar")).toBeVisible();
  await expect(page.locator(".top-card").first()).toBeVisible();

  await page.locator(".top-card").first().click();
  await expect(page.getByText("仓位与执行")).toBeVisible();
  await expect(page.getByText("关键风险与反证")).toBeVisible();
});
