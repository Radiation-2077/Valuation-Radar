import { expect, test } from "@playwright/test";

test("shows schedule controls and update history", async ({ page }) => {
  await page.goto("/updates");

  await expect(page.getByRole("heading", { name: "让排名停留在最近一次收盘。" })).toBeVisible();
  await expect(page.getByText("收盘后更新设置")).toBeVisible();
  await expect(page.getByLabel("更新频率")).toBeVisible();
  await expect(page.getByLabel("执行时间")).toBeVisible();
  await expect(page.getByRole("button", { name: "保存设置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "立即刷新行情" })).toBeVisible();
  await expect(page.getByText("最近任务")).toBeVisible();
});
