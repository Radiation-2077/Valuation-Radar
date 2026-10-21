import { expect, test } from "@playwright/test";

test("shows schedule controls and update history", async ({ page }) => {
  await page.goto("/updates");

  await expect(page.getByRole("heading", { name: "数据更新与运行状态" })).toBeVisible();
  await expect(page.locator(".latest-task-tag")).toContainText("最近任务：");
  await expect(page.getByText("DATA OPERATIONS / 02")).toHaveCount(0);
  await expect(page.getByText("让排名停留在最近一次收盘。")).toHaveCount(0);
  await expect(page.getByText("收盘后更新设置")).toBeVisible();
  await expect(
    page.locator(".n-form-item").filter({ hasText: "更新频率" }).locator(".n-select"),
  ).toBeVisible();
  await expect(
    page.locator(".n-form-item").filter({ hasText: "执行时间" }).locator(".n-time-picker"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "保存设置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "立即刷新行情" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近任务" })).toBeVisible();
  await expect(page.getByRole("button", { name: "清除所有" })).toBeVisible();

  const debugButton = page.getByRole("button", { name: "Debug 信息" }).first();
  await expect(debugButton).toBeVisible();
  await debugButton.click();
  await expect(page.getByText("事件流")).toBeVisible();
  await expect(page.getByText("STDOUT / JSONL")).toBeVisible();
  await expect(page.getByRole("button", { name: "收起 Debug" })).toBeVisible();
});
