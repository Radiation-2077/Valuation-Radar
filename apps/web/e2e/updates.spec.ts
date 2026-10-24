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

  const codexRow = page
    .locator(".n-data-table-tr")
    .filter({ hasText: "Codex 重估" })
    .first();
  const expandButton = codexRow.locator(".n-data-table-expand-trigger");
  const columnWidthsBefore = await page
    .locator(".jobs-panel .n-data-table thead th")
    .evaluateAll((cells) => cells.map((cell) => cell.getBoundingClientRect().width));
  await expect(expandButton).toBeVisible();
  await expandButton.click();
  await expect(page.getByText("任务事件流")).toBeVisible();
  await expect(page.getByText("Codex 事件流")).toBeVisible();
  await expect(page.getByText("Codex 当前动作")).toBeVisible();
  await expect(page.getByRole("button", { name: "刷新 Debug" })).toBeVisible();
  await expect(page.getByText("Codex 实时输出")).toHaveCount(0);
  await expect(page.getByText(/任务 #\d+ Debug/)).toBeVisible();
  const columnWidthsAfter = await page
    .locator(".jobs-panel .n-data-table thead th")
    .evaluateAll((cells) => cells.map((cell) => cell.getBoundingClientRect().width));
  columnWidthsAfter.forEach((width, index) => {
    expect(width).toBeCloseTo(columnWidthsBefore[index], 0);
  });
});

test("shows live elapsed time and stable parallel debug streams", async ({ page }) => {
  const startedAt = new Date(Date.now() - 5_000).toISOString();
  const job = {
    id: 999,
    job_type: "valuation_refresh",
    trigger: "manual",
    scope: "instrument:2",
    status: "running",
    phase: "valuing",
    scheduled_for: "2026-10-22T01:00:00",
    started_at: startedAt,
    finished_at: null,
    error: "",
    details: { instrument: "测试标的" },
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
    const milestoneStart = Math.max(0, debugCalls - 3);
    const codexEvents = Array.from(
      { length: Math.min(debugCalls, 3) },
      (_, index) => ({
        sequence: milestoneStart + index + 1,
        kind: "milestone",
        message: `Codex milestone ${milestoneStart + index + 1}`,
      }),
    );
    await route.fulfill({
      json: {
        job,
        events,
        ai_runs: [
          {
            id: 1,
            status: "running",
            model: "test-model",
            cli_version: "codex-test",
            exit_code: null,
            prompt_path: "",
            output_path: "",
            stderr: "",
            metadata: {},
            started_at: startedAt,
            finished_at: null,
            token_usage: {
              input_tokens: 1200,
              cached_input_tokens: 900,
              output_tokens: 80,
              reasoning_output_tokens: 20,
            },
          },
        ],
        current_action: `正在核验第 ${debugCalls} 批数据`,
        codex_events: codexEvents,
      },
    });
  });

  await page.goto("/updates");
  await expect(page.getByText("Codex 重估", { exact: true })).toBeVisible();
  await expect(page.getByText("#999", { exact: true })).toBeVisible();
  await expect(page.getByText("测试标的", { exact: true })).toBeVisible();
  await expect(page.getByText("测试标的 ·")).toHaveCount(0);
  const duration = page.locator('[data-job-duration="999"]');
  await expect(duration).toBeVisible();
  const initialDuration = Number.parseInt((await duration.innerText()).replace(/\D/g, ""), 10);
  await page.waitForTimeout(1_200);
  const nextDuration = Number.parseInt((await duration.innerText()).replace(/\D/g, ""), 10);
  expect(nextDuration).toBeGreaterThan(initialDuration);

  await page.locator(".n-data-table-expand-trigger").first().click();
  const eventStream = page.locator(".debug-events--task");
  const codexStream = page.locator(".debug-events--codex");
  await expect(page.getByText("Codex 当前动作")).toBeVisible();
  await expect(page.getByText("输入 Token", { exact: true })).toBeVisible();
  await expect(page.getByText("1,200", { exact: true })).toBeVisible();
  await expect(page.getByText("Codex 实时输出")).toHaveCount(0);
  const refreshButton = page.getByRole("button", { name: "刷新 Debug" });
  await expect(eventStream).toBeVisible();
  await expect(codexStream).toBeVisible();

  const before = {
    events: await eventStream.boundingBox(),
    codex: await codexStream.boundingBox(),
    codexCount: await codexStream.locator(".n-timeline-item").count(),
    firstCodex: await codexStream.locator(".n-timeline-item").first().innerText(),
    button: await refreshButton.boundingBox(),
    calls: debugCalls,
  };
  await expect.poll(() => debugCalls).toBeGreaterThan(before.calls + 1);
  await expect(codexStream).toContainText(before.firstCodex);
  expect(await codexStream.locator(".n-timeline-item").count()).toBeGreaterThan(
    before.codexCount,
  );
  const after = {
    events: await eventStream.boundingBox(),
    codex: await codexStream.boundingBox(),
    button: await refreshButton.boundingBox(),
  };

  expect(after.events?.height).toBeCloseTo(before.events?.height ?? 0, 0);
  expect(after.codex?.height).toBeCloseTo(before.codex?.height ?? 0, 0);
  expect(after.button?.width).toBeCloseTo(before.button?.width ?? 0, 0);
});

test("creates a manual refresh job without secure-context randomUUID", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(globalThis.crypto, "randomUUID", {
      configurable: true,
      value: undefined,
    });
  });
  let idempotencyKey = "";
  await page.route("**/api/v1/jobs", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    idempotencyKey = route.request().headers()["idempotency-key"] ?? "";
    await route.fulfill({
      status: 202,
      json: {
        id: 1000,
        job_type: "market_refresh",
        trigger: "manual",
        scope: "all",
        status: "queued",
        phase: "queued",
        scheduled_for: new Date().toISOString(),
        started_at: null,
        finished_at: null,
        error: "",
        details: {},
        created_at: new Date().toISOString(),
      },
    });
  });

  await page.goto("/updates");
  expect(await page.evaluate(() => typeof globalThis.crypto.randomUUID)).toBe("undefined");
  await page.getByRole("button", { name: "立即刷新行情" }).click();
  await expect.poll(() => idempotencyKey).toMatch(/^manual-\d+-/);
});

test("uses a distinct debug layout for market refresh jobs", async ({ page }) => {
  const job = {
    id: 1001,
    job_type: "market_refresh",
    trigger: "manual",
    scope: "all",
    status: "succeeded",
    phase: "completed",
    scheduled_for: "2026-10-22T01:00:00",
    started_at: "2026-10-22T01:00:01",
    finished_at: "2026-10-22T01:00:20",
    error: "",
    details: {
      listings: 2,
      quotes_fetched: 2,
      quotes_saved: 1,
      quotes_unchanged: 1,
      macro_observations: 3,
      ranking_runs: 3,
      latest_quote_at: "2026-10-22T01:00:10",
      errors: [],
    },
    created_at: "2026-10-22T01:00:00",
  };
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [job] } }),
  );
  await page.route("**/api/v1/jobs/1001/debug", (route) =>
    route.fulfill({
      json: {
        job,
        events: [
          {
            at: "2026-10-22T01:00:01.000Z",
            phase: "fetching",
            message: "开始抓取最新行情",
          },
        ],
        ai_runs: [],
        current_action: "任务已完成",
        codex_events: [],
      },
    }),
  );

  await page.goto("/updates");
  const row = page.locator(".n-data-table-tr").filter({ hasText: "行情刷新" }).first();
  await expect(row).toBeVisible();
  await expect(row.locator("td").nth(3)).toHaveText("—");
  await row.locator(".n-data-table-expand-trigger").click();
  await expect(page.getByText("刷新结果", { exact: true })).toBeVisible();
  await expect(page.getByText(/^有效行情/)).toBeVisible();
  await expect(page.getByText("Codex 当前动作", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Codex 事件流", { exact: true })).toHaveCount(0);
});

test("keeps only one task expanded and switches to the newly opened task", async ({ page }) => {
  const makeJob = (id: number, instrument: string) => ({
    id,
    job_type: "valuation_refresh",
    trigger: "manual",
    scope: `instrument:${id}`,
    status: "succeeded",
    phase: "awaiting_review",
    scheduled_for: null,
    started_at: "2026-10-24T01:00:00",
    finished_at: "2026-10-24T01:01:00",
    error: "",
    details: { instrument },
    created_at: "2026-10-24T01:00:00",
  });
  const jobs = [makeJob(998, "测试标的甲"), makeJob(999, "测试标的乙")];
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: jobs } }),
  );
  for (const job of jobs) {
    await page.route(`**/api/v1/jobs/${job.id}/debug`, (route) =>
      route.fulfill({
        json: {
          job,
          events: [],
          ai_runs: [],
          current_action: "Codex 执行完成",
          codex_events: [],
        },
      }),
    );
  }

  await page.goto("/updates");
  const expandTriggers = page.locator(".n-data-table-expand-trigger");
  await expect(expandTriggers).toHaveCount(2);

  await expandTriggers.nth(0).click();
  await expect(page.getByText("任务 #998 Debug", { exact: true })).toBeVisible();
  await expect(page.getByText("任务 #999 Debug", { exact: true })).toHaveCount(0);

  await expandTriggers.nth(1).click();
  await expect(page.getByText("任务 #999 Debug", { exact: true })).toBeVisible();
  await expect(page.getByText("任务 #998 Debug", { exact: true })).toHaveCount(0);
});
