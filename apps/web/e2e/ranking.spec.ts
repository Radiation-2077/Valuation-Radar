import { expect, test } from "@playwright/test";

test("switches risk profile and opens a valuation detail", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "风险调整后的性价比" })).toBeVisible();
  await expect(page.getByText("DECISION SYSTEM / LIVE RANK")).toHaveCount(0);
  await expect(page.getByText("把估值结论，压缩成可执行的排序。")).toHaveCount(0);
  await expect(page.locator(".dashboard-stale-tag")).toBeVisible();
  await expect(page.getByText("排名计算")).toHaveCount(0);
  await expect(page.getByText("最新估值")).toHaveCount(0);
  await expect(page.getByText("最新行情")).toHaveCount(0);
  await expect(page.getByText("排序单元")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "性价比Top3" })).toBeVisible();
  await expect(page.locator(".top-card")).toHaveCount(3);
  await expect(page.locator(".top-card.rank-1")).toHaveCount(1);
  await expect(page.locator(".top-card.rank-2")).toHaveCount(1);
  await expect(page.locator(".top-card.rank-3")).toHaveCount(1);
  const topCardBoxes = await page.locator(".top-card").evaluateAll((cards) =>
    cards.map((card) => card.getBoundingClientRect().height),
  );
  expect(Math.max(...topCardBoxes) - Math.min(...topCardBoxes)).toBeLessThan(1);
  await expect(page.locator(".top-thesis").first()).toHaveCSS("-webkit-line-clamp", "4");
  await expect(page.getByRole("table").first()).toBeVisible();

  const aggressiveButton = page.getByRole("button", { name: "进取", exact: true });
  await expect(page.locator(".profile-switcher").getByRole("button")).toHaveCount(3);
  await aggressiveButton.click();
  await page.waitForSelector(".profile-slide-left-enter-active");
  await expect(page.locator(".n-spin")).toHaveCount(0);
  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(aggressiveButton).toHaveAttribute("aria-pressed", "true");

  const firstCard = page.locator(".top-card").first();
  await expect(firstCard).toContainText("宁德时代");
  await firstCard.click();

  await expect(page).toHaveURL(/profile=aggressive/);
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.locator(".n-drawer .detail-panel h1")).toContainText("宁德时代");
  await expect(page.getByRole("heading", { name: "决策仪表盘" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /一、标的质地/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /二、产业周期定位/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /三、跨市场校正/ })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /A\/H 溢价分解：/ }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /A 股估值/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /H 股估值/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /六、操作建议与仓位管理/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /七、预期收益率/ })).toBeVisible();
  expect(await page.locator(".n-drawer canvas").count()).toBeGreaterThanOrEqual(6);
});

test("keeps the ranking usable on a narrow screen", async ({ page }) => {
  await page.goto("/?profile=balanced");

  await expect(
    page.getByRole("button", { name: "均衡", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".status-card")).toHaveCount(0);
  await expect(page.locator(".top-card").first()).toBeVisible();
  await expect(page.locator(".etf-table")).toBeVisible();
  await expect(page.locator(".excluded-table")).toBeVisible();
  await expect(page.getByText("只看估值偏旧")).toHaveCount(0);

  await page.locator(".top-card").first().click();
  await expect(page.locator(".n-drawer")).toBeVisible();
  await expect(page.getByRole("heading", { name: /六、操作建议与仓位管理/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /八、风险提示/ })).toBeVisible();
  await expect(page).toHaveURL(/profile=balanced/);
});

test("risk profile controls do not overlap the top three container", async ({ page }) => {
  await page.setViewportSize({ width: 960, height: 720 });
  await page.goto("/?profile=conservative");
  await page.waitForSelector(".top3-card");

  const profileBox = await page.locator(".profile-switcher").boundingBox();
  const topThreeBox = await page.locator(".top3-card").boundingBox();
  expect(profileBox).not.toBeNull();
  expect(topThreeBox).not.toBeNull();
  expect(profileBox!.y + profileBox!.height).toBeLessThan(topThreeBox!.y);
});

test("dashboard and update cards keep consistent spacing and heights", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");

  const analysisCard = page.locator(".analysis-card");
  const staleTag = await page.locator(".dashboard-stale-tag").boundingBox();
  const titleBox = await page.locator(".dashboard-title").boundingBox();
  const toolbarBox = await page.locator(".toolbar").boundingBox();
  const topThreeBox = await page.locator(".top3-card").boundingBox();
  expect(staleTag).not.toBeNull();
  expect(titleBox).not.toBeNull();
  expect(toolbarBox).not.toBeNull();
  expect(topThreeBox).not.toBeNull();
  expect(titleBox!.y - (staleTag!.y + staleTag!.height)).toBeCloseTo(8, 0);
  expect(toolbarBox!.y - (titleBox!.y + titleBox!.height)).toBeCloseTo(4, 0);
  expect(topThreeBox!.y - (toolbarBox!.y + toolbarBox!.height)).toBeCloseTo(12, 0);
  const profileSwitcherBox = await page.locator(".profile-switcher").boundingBox();
  const filterButtonBox = await page.getByRole("button", { name: "筛选" }).boundingBox();
  expect(profileSwitcherBox).not.toBeNull();
  expect(filterButtonBox).not.toBeNull();
  expect(profileSwitcherBox!.height).toBeCloseTo(filterButtonBox!.height, 0);
  await expect(analysisCard).toBeVisible();
  await expect(analysisCard.locator(".n-select")).toHaveCount(0);
  await expect(analysisCard.locator(".scatter-chart")).toBeVisible();
  const chartBox = await analysisCard.locator(".scatter-chart").boundingBox();
  expect(chartBox).not.toBeNull();
  expect(chartBox!.height).toBeGreaterThanOrEqual(540);
  expect(chartBox!.width).toBeGreaterThan(chartBox!.height);
  await expect(page.locator(".filter-card")).toHaveCount(0);
  await expect(page.locator(".filter-popover")).toHaveCount(0);
  const layoutBeforeFilters = await page.locator(".top3-card").boundingBox();
  await page.getByRole("button", { name: "筛选" }).click();
  await expect(page.locator(".filter-popover")).toBeVisible();
  await expect(page.locator(".filter-popover .n-select")).toHaveCount(3);
  await expect(page.locator(".filter-popover .n-select").first()).toBeVisible();
  await page.locator(".filter-popover .n-select").first().click();
  await expect(page.getByText("中国市场", { exact: true })).toHaveCount(0);
  await expect(page.getByText("中国 ETF", { exact: true })).toHaveCount(0);
  const layoutAfterFilters = await page.locator(".top3-card").boundingBox();
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
  const hero = await page.locator(".updates-title").boundingBox();
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

test("filtered top three keeps gold silver bronze positions", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "筛选" }).click();
  await page.locator(".filter-popover .n-select").first().click();
  await page.locator(".n-base-select-option").filter({ hasText: "H 股" }).click();
  await page.keyboard.press("Escape");

  await expect(page.locator(".top-card.rank-1")).toHaveCount(1);
  await expect(page.locator(".top-card.rank-2")).toHaveCount(1);
  await expect(page.locator(".top-card.rank-3")).toHaveCount(1);
  await expect(page.locator(".top-card.rank-1 .top-rank")).toHaveText("01");
  await expect(page.locator(".top-card.rank-2 .top-rank")).toHaveText("02");
  await expect(page.locator(".top-card.rank-3 .top-rank")).toHaveText("03");
});
