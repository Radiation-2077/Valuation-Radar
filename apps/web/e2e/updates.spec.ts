import { expect, test } from "@playwright/test";

test("uses readable execution workflow text in light mode", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/updates");

  const firstStep = page.locator(".schedule-summary .n-step").first();
  await expect(firstStep.locator(".n-step-content-header__title")).toHaveCSS(
    "color",
    "rgb(32, 52, 63)",
  );
  await expect(firstStep.locator(".n-step-content__description")).toHaveCSS(
    "color",
    "rgb(63, 89, 102)",
  );
});

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
    .filter({ hasText: "Codex 估值" })
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

test("shows final review stage for approved and rejected candidates", async ({ page }) => {
  const baseJob = {
    job_type: "valuation_refresh",
    trigger: "manual",
    status: "succeeded",
    scheduled_for: "2026-10-25T01:00:00",
    started_at: "2026-10-25T01:00:00",
    finished_at: "2026-10-25T01:10:00",
    error: "",
    created_at: "2026-10-25T01:00:00",
  };
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            ...baseJob,
            id: 802,
            scope: "instrument:2",
            phase: "review_rejected",
            details: { instrument: "已拒绝标的", review_status: "rejected" },
          },
          {
            ...baseJob,
            id: 801,
            scope: "instrument:1",
            phase: "review_approved",
            details: { instrument: "已同意标的", review_status: "published" },
          },
        ],
      },
    }),
  );

  await page.goto("/updates");
  const approved = page.locator(".n-data-table-tr").filter({ hasText: "#801" });
  const rejected = page.locator(".n-data-table-tr").filter({ hasText: "#802" });
  await expect(approved).toContainText("已同意");
  await expect(rejected).toContainText("已拒绝");
});

test("uses latest activity and shows cumulative execution time", async ({ page }) => {
  const jobs = [
    {
      id: 902,
      job_type: "valuation_refresh",
      trigger: "manual",
      scope: "instrument:5",
      status: "interrupted",
      phase: "interrupted",
      scheduled_for: null,
      started_at: "2026-10-25T01:00:00",
      finished_at: "2026-10-25T01:05:00",
      error: "服务重启时任务仍在执行",
      details: { instrument: "较早任务", failed_phase: "valuing" },
      created_at: "2026-10-25T01:00:00",
    },
    {
      id: 901,
      job_type: "valuation_refresh",
      trigger: "manual",
      scope: "instrument:4",
      status: "succeeded",
      phase: "review_approved",
      scheduled_for: null,
      started_at: "2026-10-25T01:10:00",
      finished_at: "2026-10-25T01:20:00",
      error: "",
      details: {
        instrument: "最近任务",
        execution_seconds: 615,
        resume_count: 2,
      },
      created_at: "2026-10-25T01:10:00",
    },
  ];
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: jobs } }),
  );

  await page.goto("/updates");
  await expect(page.locator(".schedule-summary").getByText("#901 · 已同意")).toBeVisible();
  await expect(page.locator('[data-job-duration="901"]')).toHaveText("累计 10 分 15 秒");
  await expect(page.getByText("服务重启导致任务中断")).toHaveCount(0);
});

test("explains an interruption with its actual phase", async ({ page }) => {
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: 903,
            job_type: "valuation_refresh",
            trigger: "manual",
            scope: "instrument:4",
            status: "interrupted",
            phase: "interrupted",
            scheduled_for: null,
            started_at: "2026-10-25T01:00:00",
            finished_at: "2026-10-25T01:02:05",
            error: "服务重启时任务仍在执行，已停止；可恢复后继续",
            details: {
              instrument: "香港证券ETF",
              failed_phase: "validating",
              interruption_kind: "service_restart",
              execution_seconds: 125,
            },
            created_at: "2026-10-25T01:00:00",
          },
        ],
      },
    }),
  );

  await page.goto("/updates");
  await expect(page.getByText("服务重启导致任务中断", { exact: true })).toBeVisible();
  await expect(
    page.getByText("任务在校验候选阶段中断，累计执行 2 分 5 秒；可点击“恢复”继续。"),
  ).toBeVisible();
});

test("allows a rejected candidate to request a new Codex valuation", async ({ page }) => {
  let requestedInstrument = 0;
  let deletedReview = 0;
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route("**/api/v1/reviews", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route("**/api/v1/reviews/rejected?limit=20", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            report_id: 10,
            instrument_id: 4,
            name: "香港证券ETF",
            analysis_date: "2026-10-25",
            generated_at: "2026-10-25T02:00:00",
            thesis: "ETF 前十大代表 PB 需要重新核对。",
            confidence: "中",
            markets: [
              {
                valuation_market_id: 14,
                market: "CN",
                code: "513090.SH",
                currency: "CNY",
                price: 1.624,
                fair_mid: 1.2,
                verdict: "等待回落",
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/instruments/4/revaluations", (route) => {
    requestedInstrument = 4;
    return route.fulfill({
      status: 202,
      json: {
        id: 77,
        job_type: "valuation_refresh",
        trigger: "manual",
        scope: "instrument:4",
        status: "queued",
        phase: "queued",
        scheduled_for: null,
        started_at: null,
        finished_at: null,
        error: "",
        details: { instrument: "香港证券ETF" },
        created_at: "2026-10-25T02:10:00",
      },
    });
  });
  await page.route("**/api/v1/reviews/10", (route) => {
    deletedReview = 10;
    return route.fulfill({ json: { report_id: 10, deleted: true } });
  });

  await page.goto("/updates");
  await expect(page.getByRole("heading", { name: "已拒绝候选" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "删除已拒绝候选 香港证券ETF" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "删除已拒绝候选 香港证券ETF" }).click();
  await page.locator(".n-popconfirm").getByRole("button", { name: "删除" }).click();
  await expect.poll(() => deletedReview).toBe(10);
  await expect(page.getByText("已删除拒绝候选")).toBeVisible();
  await page.getByRole("button", { name: "重新估值 香港证券ETF" }).click();
  await page.getByRole("button", { name: "开始估值" }).click();

  expect(requestedInstrument).toBe(4);
  await expect(page.getByText("Codex 估值任务 #77 已加入队列")).toBeVisible();
});

test("resumes an interrupted Codex valuation job", async ({ page }) => {
  let resumedJob = 0;
  const interruptedJob = {
    id: 808,
    job_type: "valuation_refresh",
    trigger: "manual",
    scope: "instrument:4",
    status: "interrupted",
    phase: "interrupted",
    scheduled_for: null,
    started_at: "2026-10-25T01:00:00",
    finished_at: "2026-10-25T01:16:00",
    error: "服务重启导致任务中断，可恢复后重新执行",
    details: { instrument: "香港证券ETF", failed_phase: "valuing" },
    created_at: "2026-10-25T01:00:00",
  };

  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [interruptedJob] } }),
  );
  await page.route("**/api/v1/jobs/808/resume", (route) => {
    resumedJob = 808;
    return route.fulfill({
      status: 202,
      json: { ...interruptedJob, status: "queued", phase: "queued", error: "" },
    });
  });

  await page.goto("/updates");
  const row = page.locator(".n-data-table-tr").filter({ hasText: "#808" });
  await expect(row).toContainText("已中断");
  await row.getByRole("button", { name: "恢复任务 #808" }).click();

  expect(resumedJob).toBe(808);
  await expect(page.getByText("任务 #808 已恢复并重新排队")).toBeVisible();
});

test("pauses a running Codex valuation job", async ({ page }) => {
  let pausedJob = 0;
  const runningJob = {
    id: 809,
    job_type: "valuation_refresh",
    trigger: "manual",
    scope: "instrument:4",
    status: "running",
    phase: "valuing",
    scheduled_for: null,
    started_at: "2026-10-25T01:00:00",
    finished_at: null,
    error: "",
    details: { instrument: "香港证券ETF" },
    created_at: "2026-10-25T01:00:00",
  };

  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [runningJob] } }),
  );
  await page.route("**/api/v1/jobs/809/pause", (route) => {
    pausedJob = 809;
    return route.fulfill({
      json: {
        ...runningJob,
        status: "paused",
        phase: "paused",
        finished_at: "2026-10-25T01:05:00",
        details: {
          ...runningJob.details,
          paused_from_phase: "valuing",
        },
      },
    });
  });

  await page.goto("/updates");
  const row = page.locator(".n-data-table-tr").filter({ hasText: "#809" });
  await row.getByRole("button", { name: "暂停任务 #809" }).click();

  expect(pausedJob).toBe(809);
  await expect(page.getByText("任务 #809 已暂停")).toBeVisible();
});

test("confirms a running job deletion in one modal", async ({ page }) => {
  let deleteCalls = 0;
  const runningJob = {
    id: 804,
    job_type: "valuation_refresh",
    trigger: "manual",
    scope: "instrument:4",
    status: "running",
    phase: "valuing",
    scheduled_for: null,
    started_at: "2026-10-25T01:00:00",
    finished_at: null,
    error: "",
    details: { instrument: "香港证券ETF" },
    created_at: "2026-10-25T01:00:00",
  };
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [runningJob] } }),
  );
  await page.route("**/api/v1/jobs/804", (route) => {
    deleteCalls += 1;
    return route.fulfill({
      json: { job_id: 804, deleted: true, terminated: true },
    });
  });

  await page.goto("/updates");
  await page.getByRole("button", { name: "删除任务 #804" }).click();
  await expect(page.getByText("确认删除任务", { exact: true })).toBeVisible();
  await expect(page.getByText("确认后会立即终止 Codex 子进程")).toBeVisible();
  await expect(page.getByText("此操作不可恢复，确定永久删除吗？")).toBeVisible();
  expect(deleteCalls).toBe(0);

  await page.getByRole("button", { name: "确认删除", exact: true }).click();
  await expect.poll(() => deleteCalls).toBe(1);
  await expect(page.getByText("任务 #804 已终止并删除")).toBeVisible();
});

test("previews a pending review before approval", async ({ page }) => {
  let approvedReport = 0;
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route("**/api/v1/reviews/rejected?limit=20", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route("**/api/v1/reviews", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            report_id: 10,
            instrument_id: 4,
            name: "香港证券ETF",
            analysis_date: "2026-10-25",
            generated_at: "2026-10-25T02:00:00",
            thesis: "ETF 前十大代表 PB 与净值折价需要共同核验。",
            confidence: "中",
            markets: [
              {
                valuation_market_id: 14,
                market: "CN",
                code: "513090.SH",
                currency: "CNY",
                price: 1.624,
                fair_mid: 1.2,
                verdict: "等待回落",
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/valuations/14?profile=balanced", (route) =>
    route.fulfill({
      json: {
        valuation_market_id: 14,
        latest_valuation_market_id: 14,
        report_id: 10,
        instrument_id: 4,
        name: "香港证券ETF",
        market: "CN",
        code: "513090.SH",
        currency: "CNY",
        asset_type: "etf",
        path: "etf",
        industry: "证券",
        analysis_date: "2026-10-25",
        generated_at: "2026-10-25T02:00:00",
        price_date: "2026-10-24",
        stale_days: 1,
        quality: { rating: 3, label: "良好", score: 72, moat: "", gate_pass: true, gate_reason: "" },
        cycle: { stage: "成熟期", position: 0.5 },
        conclusion: { verdict: "等待回落", thesis: "候选预览", confidence: "中" },
        price: 1.624,
        baseline_price: 1.624,
        current_price: 1.624,
        fair_low: 1.4,
        fair_mid: 1.5,
        fair_high: 1.6,
        safety_margin_pct: -8.3,
        effective_safety_margin_pct: -8.3,
        valuation: { pe: 21.4, pb: 0.87 },
        gauges: {},
        expected_return: {},
        downside: {},
        position: {},
        verdict: "等待回落",
        score: { margin: 40, base: 60, risk: 55, stability: 70, total: 56, band: "B" },
        risks: [],
        missing: [],
        notes: "",
        risk_flags: [],
        excluded_reasons: [],
        same_company: [],
        macro: {},
        report_detail: { sections: [], foot: "" },
      },
    }),
  );
  await page.route("**/api/v1/reviews/10/approve", (route) => {
    approvedReport = 10;
    return route.fulfill({
      json: { report_id: 10, status: "published", ranking_rebuilt: true },
    });
  });

  await page.goto("/updates");
  await page.getByRole("button", { name: "预览 香港证券ETF" }).click();
  await expect(page.getByText("候选估值预览", { exact: true })).toBeVisible();
  const actions = page.locator(".review-preview-actions");
  await expect(actions).toBeVisible();
  const before = await actions.boundingBox();
  await page.locator(".review-preview-body").evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  const after = await actions.boundingBox();
  expect(Math.abs((after?.y ?? 0) - (before?.y ?? 0))).toBeLessThan(1);
  await page.getByRole("button", { name: "批准并发布" }).click();

  await expect.poll(() => approvedReport).toBe(10);
  await expect(page.getByText("候选估值预览", { exact: true })).toHaveCount(0);
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
            status: "paused",
            model: "test-model",
            cli_version: "codex-test",
            exit_code: -3,
            prompt_path: "",
            output_path: "",
            stderr: "",
            metadata: { thread_id: "thread-test" },
            started_at: startedAt,
            finished_at: startedAt,
            token_usage: {
              input_tokens: 1200,
              cached_input_tokens: 900,
              output_tokens: 80,
              reasoning_output_tokens: 20,
            },
          },
          {
            id: 2,
            status: "running",
            model: "test-model",
            cli_version: "codex-test",
            exit_code: null,
            prompt_path: "",
            output_path: "",
            stderr: "",
            metadata: {
              thread_id: "thread-test",
              resume_session_id: "thread-test",
            },
            started_at: startedAt,
            finished_at: null,
            token_usage: {
              input_tokens: 300,
              cached_input_tokens: 200,
              output_tokens: 30,
              reasoning_output_tokens: 10,
            },
          },
        ],
        current_action: `正在核验第 ${debugCalls} 批数据`,
        codex_events: codexEvents,
      },
    });
  });

  await page.goto("/updates");
  await expect(page.getByText("Codex 估值", { exact: true })).toBeVisible();
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
  await expect(page.getByText("Codex 会话", { exact: true })).toHaveCount(1);
  await expect(page.getByText("共 2 次执行", { exact: true })).toBeVisible();
  await expect(page.getByText("Codex 运行", { exact: false })).toHaveCount(0);
  await expect(page.getByText("输入 Token", { exact: true })).toBeVisible();
  await expect(page.getByText("1,500", { exact: true })).toBeVisible();
  await expect(page.getByText("thread-test", { exact: true })).toBeVisible();
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
  await page.route("**/api/v1/jobs?limit=20", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
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
