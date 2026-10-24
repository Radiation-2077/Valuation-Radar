import { expect, test } from "@playwright/test";

test("keeps the browser title in sync with routes and valuation drawer", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("性价比排名 · 估值雷达");

  await page.goto("/updates");
  await expect(page).toHaveTitle("更新中心 · 估值雷达");

  await page.goto("/");
  await page.locator(".top-card").first().click();
  await expect(page).toHaveTitle(/^.+\s[AH]\s·\s估值雷达$/);
  await page.getByRole("button", { name: "关闭详情" }).click();
  await expect(page).toHaveTitle("性价比排名 · 估值雷达");

  await page.goto("/valuations/invalid");
  await expect(page).toHaveTitle("估值详情 · 估值雷达");
});
