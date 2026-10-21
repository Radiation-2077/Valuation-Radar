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
  await expect(
    page.getByRole("button", { name: /立即刷新行情|已有任务执行中/ }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近任务" })).toBeVisible();
  await expect(page.getByRole("button", { name: "清除所有" })).toBeVisible();

  const debugButton = page.getByRole("button", { name: "Debug 信息" }).first();
  await expect(debugButton).toBeVisible();
  await debugButton.click();
  await expect(page.getByText("事件流")).toBeVisible();
  await expect(page.getByRole("button", { name: "刷新 Debug" })).toBeVisible();
  await expect(page.getByText("Codex 实时输出")).toBeVisible();
  await expect(page.getByRole("button", { name: "收起 Debug" })).toBeVisible();
});

test("keeps the debug panel geometry stable while live output grows", async ({ page }) => {
  const job = {
    id: 999,
    job_type: "valuation_refresh",
    trigger: "manual",
    scope: "instrument:2",
    status: "running",
    phase: "valuing",
    scheduled_for: "2026-10-22T01:00:00",
    started_at: "2026-10-22T01:00:01",
    finished_at: null,
    error: "",
    details: {},
    created_at: "2026-10-22T01:00:00",
  };
  let debugCalls = 0;

  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [job] } }),
  );
  await page.route("**/api/v1/jobs/999/debug", async (route) => {
    debugCalls += 1;
    const events = Array.from({ length: Math.min(debugCalls + 1, 12) }, (_, index) => ({
      at: `2026-10-22T01:00:${String(index).padStart(2, "0")}.000Z`,
      phase: "valuing",
      message: `实时事件 ${index + 1}`,
    }));
    const stdout = Array.from(
      { length: debugCalls * 8 },
      (_, index) =>
        JSON.stringify({
          type: "item.completed",
          item: { type: "agent_message", text: `输出 ${index + 1}` },
        }),
    ).join("\n");
    await route.fulfill({
      json: { job, events, ai_runs: [], stdout, stderr: "" },
    });
  });

  await page.goto("/updates");
  await page.getByRole("button", { name: "Debug 信息" }).first().click();
  const eventStream = page.locator(".debug-events");
  const readableLog = page.getByLabel("Codex 可读输出");
  const refreshButton = page.getByRole("button", { name: "刷新 Debug" });
  await expect(eventStream).toBeVisible();

  const before = {
    events: await eventStream.boundingBox(),
    log: await readableLog.boundingBox(),
    button: await refreshButton.boundingBox(),
    calls: debugCalls,
  };
  await expect.poll(() => debugCalls).toBeGreaterThan(before.calls + 1);
  const after = {
    events: await eventStream.boundingBox(),
    log: await readableLog.boundingBox(),
    button: await refreshButton.boundingBox(),
  };

  expect(after.events?.height).toBeCloseTo(before.events?.height ?? 0, 0);
  expect(after.log?.height).toBeCloseTo(before.log?.height ?? 0, 0);
  expect(after.button?.width).toBeCloseTo(before.button?.width ?? 0, 0);
});
