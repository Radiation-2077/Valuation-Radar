import { expect, test } from "@playwright/test";

test("switches risk profile and opens a valuation detail", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "风险调整后的性价比" })).toBeVisible();
  await expect(page.getByText("DECISION SYSTEM / LIVE RANK")).toHaveCount(0);
  await expect(page.getByText("把估值结论，压缩成可执行的排序。")).toHaveCount(0);
  await expect(page.locator(".dashboard-stale-tag")).toBeVisible();
  await expect(page.locator(".status-card").getByText(/估值超过/)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "性价比Top3" })).toBeVisible();
  await expect(page.locator(".top-card")).toHaveCount(3);
  await expect(page.getByRole("table").first()).toBeVisible();

  const aggressiveTab = page.locator('.n-tabs-tab[data-name="aggressive"]');
  await aggressiveTab.click();
  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(aggressiveTab).toHaveClass(/n-tabs-tab--active/);

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

  await expect(page.locator('.n-tabs-tab[data-name="balanced"]')).toHaveClass(
    /n-tabs-tab--active/,
  );
  await expect(page.locator(".status-card")).toBeVisible();
  await expect(page.locator(".top-card").first()).toBeVisible();
  await expect(page.locator(".etf-table")).toBeVisible();
  await expect(page.locator(".excluded-table")).toBeVisible();
  await expect(page.getByText("只看估值偏旧")).toHaveCount(0);

  await page.locator(".top-card").first().click();
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.getByText("仓位与执行")).toBeVisible();
  await expect(page.getByText("关键风险与反证")).toBeVisible();
  await expect(page).toHaveURL(/profile=balanced/);
});

test("risk profile controls do not overlap the freshness bar", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 720 });
  await page.goto("/?profile=conservative");

  const profileBox = await page.locator(".n-tabs").boundingBox();
  const freshnessBox = await page.locator(".status-card").boundingBox();
  expect(profileBox).not.toBeNull();
  expect(freshnessBox).not.toBeNull();
  expect(profileBox!.y + profileBox!.height).toBeLessThan(freshnessBox!.y);
});

test("dashboard and update cards keep consistent spacing and heights", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");

  const analysisCard = page.locator(".analysis-card");
  await expect(analysisCard).toBeVisible();
  await expect(analysisCard.locator(".n-select")).toHaveCount(0);
  await expect(analysisCard.locator(".scatter-chart")).toBeVisible();
  await expect(page.locator(".filter-card")).toHaveCount(0);
  await expect(page.locator(".filter-popover")).toHaveCount(0);
  const layoutBeforeFilters = await page.locator(".status-card").boundingBox();
  await page.getByRole("button", { name: "筛选" }).click();
  await expect(page.locator(".filter-popover")).toBeVisible();
  await expect(page.locator(".filter-popover .n-select")).toHaveCount(3);
  await expect(page.locator(".filter-popover .n-select").first()).toBeVisible();
  const layoutAfterFilters = await page.locator(".status-card").boundingBox();
  expect(layoutBeforeFilters).not.toBeNull();
  expect(layoutAfterFilters).not.toBeNull();
  expect(Math.abs(layoutBeforeFilters!.y - layoutAfterFilters!.y)).toBeLessThan(1);
  const tableShellStyle = await page.locator(".table-shell").first().evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      borderStyle: style.borderStyle,
      borderWidth: Number.parseFloat(style.borderWidth),
      paddingLeft: Number.parseFloat(style.paddingLeft),
    };
  });
  expect(tableShellStyle.borderStyle).toBe("solid");
  expect(tableShellStyle.borderWidth).toBeGreaterThanOrEqual(1);
  expect(tableShellStyle.paddingLeft).toBeGreaterThanOrEqual(10);
  const tableBottomBorder = await page.locator(".ranking-table").first().evaluate(
    (element) => getComputedStyle(element).borderBottomWidth,
  );
  expect(tableBottomBorder).toBe("0px");
  const rankingHeading = page.locator(".ranking-card").first().locator(".card-heading");
  const headingBox = await rankingHeading.locator(".n-h").boundingBox();
  const badgeBox = await rankingHeading.locator(".n-tag").boundingBox();
  expect(headingBox).not.toBeNull();
  expect(badgeBox).not.toBeNull();
  const headingCenter = headingBox!.y + headingBox!.height / 2;
  const badgeCenter = badgeBox!.y + badgeBox!.height / 2;
  expect(Math.abs(headingCenter - badgeCenter)).toBeLessThanOrEqual(1);

  await page.goto("/updates");
  const statusCards = page.locator(".ops-status-grid .n-card");
  await expect(statusCards).toHaveCount(4);
  const first = await statusCards.nth(0).boundingBox();
  const second = await statusCards.nth(1).boundingBox();
  const hero = await page.locator(".updates-hero").boundingBox();
  const statusGrid = await page.locator(".ops-status-grid").boundingBox();
  expect(first).not.toBeNull();
  expect(second).not.toBeNull();
  expect(hero).not.toBeNull();
  expect(statusGrid).not.toBeNull();
  const horizontalGap = second!.x - (first!.x + first!.width);
  const verticalGap = statusGrid!.y - (hero!.y + hero!.height);
  const configuredGap = await page.locator(".ops-status-grid").evaluate(
    (element) => Number.parseFloat(getComputedStyle(element).gap),
  );
  expect(configuredGap).toBe(20);
  expect(horizontalGap).toBeCloseTo(configuredGap, 0);
  expect(verticalGap).toBeCloseTo(configuredGap, 0);
  expect(Math.abs(horizontalGap - verticalGap)).toBeLessThanOrEqual(2);
});

test("naive scrollbar keeps page width stable between routes", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.waitForSelector(".app-scrollbar");

  const homeHeader = await page.locator(".n-layout-header").boundingBox();
  const bodyOverflow = await page.locator("body").evaluate(
    (element) => getComputedStyle(element).overflow,
  );
  expect(homeHeader).not.toBeNull();
  expect(bodyOverflow).toBe("hidden");

  await page.goto("/updates");
  await page.waitForSelector(".app-scrollbar");
  const updatesHeader = await page.locator(".n-layout-header").boundingBox();
  expect(updatesHeader).not.toBeNull();
  expect(Math.abs(homeHeader!.x - updatesHeader!.x)).toBeLessThan(1);
  expect(Math.abs(homeHeader!.width - updatesHeader!.width)).toBeLessThan(1);
});
