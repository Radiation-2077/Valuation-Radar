import { expect, test } from "@playwright/test";

test("exposes both primary routes through the mobile navigation menu", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const menuButton = page.getByRole("button", { name: "打开导航菜单" });
  await expect(menuButton).toBeVisible();
  const headerBox = await page.locator(".header-layout").boundingBox();
  const actionsBox = await page.locator(".header-actions").boundingBox();
  expect(headerBox).not.toBeNull();
  expect(actionsBox).not.toBeNull();
  expect(headerBox!.x + headerBox!.width - actionsBox!.x - actionsBox!.width).toBeLessThanOrEqual(16.5);
  await menuButton.click();

  await expect(page.getByRole("menuitem", { name: "性价比排名" })).toBeVisible();
  await page.getByRole("menuitem", { name: "更新中心" }).click();

  await expect(page).toHaveURL("/updates");
  await expect(page.getByRole("heading", { name: "数据更新与运行状态" })).toBeVisible();
  await expect(page.getByRole("button", { name: "打开导航菜单" })).toBeVisible();

  await page.getByRole("button", { name: "打开导航菜单" }).click();
  await page.getByRole("menuitem", { name: "性价比排名" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "风险调整后的性价比" })).toBeVisible();
});
