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
  const iconBoxes = await Promise.all(
    [".header-status", ".theme-toggle", ".mobile-nav-toggle"].map((selector) =>
      page.locator(selector).boundingBox(),
    ),
  );
  const iconCenters = iconBoxes.map((box) => (box ? box.x + box.width / 2 : Number.NaN));
  expect(iconCenters[1]! - iconCenters[0]!).toBeCloseTo(40, 0);
  expect(iconCenters[2]! - iconCenters[1]!).toBeCloseTo(40, 0);
  const logoBox = await page.locator(".brand-mark").boundingBox();
  const titleBox = await page.locator(".brand-copy strong").boundingBox();
  const subtitleBox = await page.locator(".brand-copy small").boundingBox();
  expect(logoBox).not.toBeNull();
  expect(titleBox).not.toBeNull();
  expect(subtitleBox).not.toBeNull();
  expect(logoBox!.y + logoBox!.height / 2 - headerBox!.height / 2).toBeCloseTo(0, 0);
  expect(subtitleBox!.y - titleBox!.y - titleBox!.height).toBeCloseTo(0, 0);
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
